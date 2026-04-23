"""记忆子系统：基于 MemoryBackend 的 MemoryStore + Consolidator + Dream。

与旧版差异：
- `MemoryStore` 不再做文件 I/O、legacy 迁移、游标文件等工作，纯粹通过
  `MemoryBackend`（默认 `MongoMemoryBackend`）操作 workspace 级长期记忆、
  history 和 cursor。
- `Consolidator` 全部 async，锁按 `session.id` 区分；token-probe 不再从 key 拆
  channel/chat_id，由上层 loop 在真正调用时补齐。
- `Dream` 简化为单次 LLM 调用 + 结构化段落解析，直接通过 MemoryBackend 写回
  memory docs；触发入口拆成 `should_trigger`，实际调度交给 AgentLoop。
"""

from __future__ import annotations

import asyncio
import re
import weakref
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from app.service.nanobot.utils.helpers import (
    estimate_message_tokens,
    estimate_prompt_tokens_chain,
    strip_think,
)
from app.service.nanobot.utils.prompt_templates import render_template

if TYPE_CHECKING:
    from app.service.nanobot.config.schema import DreamConfig
    from app.service.nanobot.providers.base import LLMProvider
    from app.service.nanobot.session.manager import Session, SessionManager
    from app.service.nanobot.storage.base import MemoryBackend


# 固定的三种长期记忆文档类型，与 NanobotMemoryDocTypeEnum 值保持一致
_DOC_MEMORY = "memory"
_DOC_SOUL = "soul"
_DOC_USER = "user"


# ---------------------------------------------------------------------------
# MemoryStore —— workspace 级 async 记忆门面
# ---------------------------------------------------------------------------


class MemoryStore:
    """workspace 级记忆门面，所有持久化操作委托 `MemoryBackend`"""

    _DEFAULT_MAX_HISTORY = 1000

    def __init__(
        self,
        backend: MemoryBackend,
        workspace_id: str,
        max_history_entries: int = _DEFAULT_MAX_HISTORY,
    ):
        self.backend = backend
        self.workspace_id = workspace_id
        self.max_history_entries = max_history_entries

    # -- 长期记忆文档：MEMORY / SOUL / USER -----------------------------------

    async def read_memory(self) -> str:
        return await self.backend.read_doc(self.workspace_id, _DOC_MEMORY)

    async def write_memory(self, content: str) -> None:
        await self.backend.write_doc(self.workspace_id, _DOC_MEMORY, content)

    async def read_soul(self) -> str:
        return await self.backend.read_doc(self.workspace_id, _DOC_SOUL)

    async def write_soul(self, content: str) -> None:
        await self.backend.write_doc(self.workspace_id, _DOC_SOUL, content)

    async def read_user(self) -> str:
        return await self.backend.read_doc(self.workspace_id, _DOC_USER)

    async def write_user(self, content: str) -> None:
        await self.backend.write_doc(self.workspace_id, _DOC_USER, content)

    async def get_memory_context(self) -> str:
        """用于 ContextBuilder 注入 prompt 的长期记忆片段"""
        long_term = await self.read_memory()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    # -- history ----------------------------------------------------------------

    async def append_history(self, entry: str) -> int:
        """追加一条 history 条目，返回原子分配的 cursor"""
        content = strip_think(entry.rstrip()) or entry.rstrip()
        return await self.backend.append_history(self.workspace_id, content)

    async def read_unprocessed_history(self, since_cursor: int) -> list[dict[str, Any]]:
        """读取 cursor > since_cursor 的所有未处理 history 条目"""
        return await self.backend.read_history(
            self.workspace_id, since_cursor=since_cursor,
        )

    async def count_unprocessed_history(self, since_cursor: int) -> int:
        """轻量统计未处理条目数（用于 Dream 触发阈值判断）"""
        entries = await self.read_unprocessed_history(since_cursor)
        return len(entries)

    async def compact_history(self) -> int:
        """按配置上限裁剪最旧 history 条目，返回删除条数"""
        if self.max_history_entries <= 0:
            return 0
        return await self.backend.compact_history(
            self.workspace_id, self.max_history_entries,
        )

    # -- cursor -----------------------------------------------------------------

    async def get_last_cursor(self) -> int:
        """已分配的最大 history cursor"""
        last_cursor, _ = await self.backend.get_cursors(self.workspace_id)
        return last_cursor

    async def get_last_dream_cursor(self) -> int:
        """Dream 已处理到的 cursor"""
        _, dream_cursor = await self.backend.get_cursors(self.workspace_id)
        return dream_cursor

    async def set_last_dream_cursor(self, cursor: int) -> None:
        await self.backend.set_dream_cursor(self.workspace_id, cursor)

    # -- fallback：LLM 总结失败时的兜底 -----------------------------------------

    async def raw_archive(self, messages: list[dict[str, Any]]) -> None:
        """Consolidation LLM 失败时把原始消息塞进 history.jsonl 做兜底"""
        content = (
            f"[RAW] {len(messages)} messages\n"
            f"{self._format_messages(messages)}"
        )
        await self.append_history(content)
        logger.warning(
            "Memory consolidation degraded: raw-archived {} messages",
            len(messages),
        )

    @staticmethod
    def _format_messages(messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for message in messages:
            if not message.get("content"):
                continue
            tools = (
                f" [tools: {', '.join(message['tools_used'])}]"
                if message.get("tools_used")
                else ""
            )
            lines.append(
                f"[{message.get('timestamp', '?')[:16]}] "
                f"{message['role'].upper()}{tools}: {message['content']}",
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Consolidator —— token 预算触发的滚动归档
# ---------------------------------------------------------------------------


class Consolidator:
    """按 token 预算把旧消息摘要并 append 到 history.jsonl"""

    _MAX_CONSOLIDATION_ROUNDS = 5
    _MAX_CHUNK_MESSAGES = 60
    _SAFETY_BUFFER = 1024

    def __init__(
        self,
        store: MemoryStore,
        provider: LLMProvider,
        model: str,
        sessions: SessionManager,
        context_window_tokens: int,
        build_messages: Callable[..., list[dict[str, Any]]],
        get_tool_definitions: Callable[[], list[dict[str, Any]]],
        max_completion_tokens: int = 4096,
    ):
        self.store = store
        self.provider = provider
        self.model = model
        self.sessions = sessions
        self.context_window_tokens = context_window_tokens
        self.max_completion_tokens = max_completion_tokens
        self._build_messages = build_messages
        self._get_tool_definitions = get_tool_definitions
        # 按 session.id 区分锁：同 session 不能并发做 consolidation
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    def get_lock(self, session_id: str) -> asyncio.Lock:
        """按 session id 取/建共享锁"""
        return self._locks.setdefault(session_id, asyncio.Lock())

    # -- 边界选取 --------------------------------------------------------------

    def pick_consolidation_boundary(
        self,
        session: Session,
        tokens_to_remove: int,
    ) -> tuple[int, int] | None:
        """找一个 user 回合的边界，使剔除的旧 prompt token 至少达到目标值"""
        start = session.last_consolidated
        if start >= len(session.messages) or tokens_to_remove <= 0:
            return None

        removed_tokens = 0
        last_boundary: tuple[int, int] | None = None
        for idx in range(start, len(session.messages)):
            message = session.messages[idx]
            if idx > start and message.get("role") == "user":
                last_boundary = (idx, removed_tokens)
                if removed_tokens >= tokens_to_remove:
                    return last_boundary
            removed_tokens += estimate_message_tokens(message)

        return last_boundary

    def _cap_consolidation_boundary(
        self,
        session: Session,
        end_idx: int,
    ) -> int | None:
        """对单轮最大消息数做夹紧，但不破坏 user-turn 对齐"""
        start = session.last_consolidated
        if end_idx - start <= self._MAX_CHUNK_MESSAGES:
            return end_idx

        capped_end = start + self._MAX_CHUNK_MESSAGES
        for idx in range(capped_end, start, -1):
            if session.messages[idx].get("role") == "user":
                return idx
        return None

    # -- token 估算 ------------------------------------------------------------

    def estimate_session_prompt_tokens(
        self,
        session: Session,
        *,
        session_summary: str | None = None,
    ) -> tuple[int, str]:
        """估算当前 prompt 体积（用于决定是否触发 consolidation）

        channel / chat_id 在新架构下暂不参与 token 估算（由上层 AgentLoop 决定
        是否带入）；为保持估算稳定这里一律传 None。
        """
        history = session.get_history(max_messages=0)
        probe_messages = self._build_messages(
            history=history,
            current_message="[token-probe]",
            channel=None,
            chat_id=None,
            session_summary=session_summary,
        )
        return estimate_prompt_tokens_chain(
            self.provider,
            self.model,
            probe_messages,
            self._get_tool_definitions(),
        )

    # -- 单次归档 --------------------------------------------------------------

    async def archive(self, messages: list[dict[str, Any]]) -> str | None:
        """把一段消息交给 LLM 做摘要并 append 到 history；失败则走 raw_archive"""
        if not messages:
            return None
        try:
            formatted = MemoryStore._format_messages(messages)
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": render_template(
                            "agent/consolidator_archive.md",
                            strip=True,
                        ),
                    },
                    {"role": "user", "content": formatted},
                ],
                tools=None,
                tool_choice=None,
            )
            if response.finish_reason == "error":
                raise RuntimeError(f"LLM returned error: {response.content}")
            summary = response.content or "[no summary]"
            await self.store.append_history(summary)
            return summary
        except Exception:
            logger.warning("Consolidation LLM call failed, raw-dumping to history")
            await self.store.raw_archive(messages)
            return None

    # -- 主入口 ----------------------------------------------------------------

    async def maybe_consolidate_by_tokens(
        self,
        session: Session,
        *,
        session_summary: str | None = None,
    ) -> None:
        """滚动归档直到 prompt 估算落回安全预算内

        预算 = context_window - max_completion - safety_buffer，目标 = 预算的一半。
        """
        if not session.messages or self.context_window_tokens <= 0:
            return

        lock = self.get_lock(session.id)
        async with lock:
            budget = (
                self.context_window_tokens
                - self.max_completion_tokens
                - self._SAFETY_BUFFER
            )
            target = budget // 2
            try:
                estimated, source = self.estimate_session_prompt_tokens(
                    session,
                    session_summary=session_summary,
                )
            except Exception:
                logger.exception("Token estimation failed for session {}", session.id)
                estimated, source = 0, "error"
            if estimated <= 0:
                return
            if estimated < budget:
                unconsolidated_count = len(session.messages) - session.last_consolidated
                logger.debug(
                    "Token consolidation idle session={}: {}/{} via {}, msgs={}",
                    session.id,
                    estimated,
                    self.context_window_tokens,
                    source,
                    unconsolidated_count,
                )
                return

            last_summary: str | None = None
            for round_num in range(self._MAX_CONSOLIDATION_ROUNDS):
                if estimated <= target:
                    break

                boundary = self.pick_consolidation_boundary(
                    session, max(1, estimated - target),
                )
                if boundary is None:
                    logger.debug(
                        "Token consolidation: no safe boundary for session {} (round {})",
                        session.id,
                        round_num,
                    )
                    break

                end_idx = boundary[0]
                end_idx = self._cap_consolidation_boundary(session, end_idx)
                if end_idx is None:
                    logger.debug(
                        "Token consolidation: no capped boundary for session {} (round {})",
                        session.id,
                        round_num,
                    )
                    break

                chunk = session.messages[session.last_consolidated:end_idx]
                if not chunk:
                    break

                logger.info(
                    "Token consolidation round {} for session={}: {}/{} via {}, chunk={} msgs",
                    round_num,
                    session.id,
                    estimated,
                    self.context_window_tokens,
                    source,
                    len(chunk),
                )
                summary = await self.archive(chunk)
                if summary:
                    last_summary = summary
                else:
                    break
                session.last_consolidated = end_idx
                await self.sessions.save(session)

                try:
                    estimated, source = self.estimate_session_prompt_tokens(
                        session,
                        session_summary=session_summary,
                    )
                except Exception:
                    logger.exception("Token estimation failed for session {}", session.id)
                    estimated, source = 0, "error"
                if estimated <= 0:
                    break

            # 把最后一次摘要写回 session.metadata，便于下次 prepare_session
            # 时注入 _last_summary（与 AutoCompact 的注入策略保持一致）
            if last_summary and last_summary != "(nothing)":
                session.metadata["_last_summary"] = {
                    "text": last_summary,
                    "last_active": session.updated_at.isoformat(),
                }
                await self.sessions.save(session)


# ---------------------------------------------------------------------------
# Dream —— 单次 LLM 全量回写版本（阈值触发，AgentLoop 侧调度）
# ---------------------------------------------------------------------------


class Dream:
    """长期记忆整理：按阈值触发，一次 LLM 调用输出三份 memory doc 的新内容

    与旧版对比：
    - 去掉了 Phase 1/Phase 2、AgentRunner、文件系统工具、skill-creator 路径；
    - 输出严格使用 `## NEW_MEMORY` / `## NEW_SOUL` / `## NEW_USER` 三段分隔，
      段内若写 `NO_CHANGE` 则跳过，否则直接 write_doc 覆盖；
    - 不再保留 tool_events/changelog 明细日志（Mongo 层审计由 updated_at 承担）。
    """

    _SECTION_RE = re.compile(
        r"^\s*##\s*NEW_(MEMORY|SOUL|USER)\s*\n(.*?)(?=\n\s*##\s*NEW_|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    def __init__(
        self,
        store: MemoryStore,
        provider: LLMProvider,
        model: str,
        config: DreamConfig,
    ):
        self.store = store
        self.provider = provider
        self.model = model
        self.config = config

    # -- 触发 --------------------------------------------------------------

    async def should_trigger(self) -> bool:
        """未处理 history 数 >= 阈值则触发（由 AgentLoop 在消息处理完成后调用）"""
        if not self.config.enabled:
            return False
        last_cursor = await self.store.get_last_dream_cursor()
        pending = await self.store.count_unprocessed_history(last_cursor)
        return pending >= self.config.trigger_unprocessed_count

    # -- 主入口 ------------------------------------------------------------

    async def run(self) -> bool:
        """处理一批未处理的 history 条目；有工作做返回 True"""
        if not self.config.enabled:
            return False

        last_cursor = await self.store.get_last_dream_cursor()
        entries = await self.store.read_unprocessed_history(since_cursor=last_cursor)
        if not entries:
            return False

        batch = entries[: self.config.max_batch_size]
        new_cursor = batch[-1]["cursor"]
        logger.info(
            "Dream: workspace={} 处理 {} 条 history (cursor {}→{}, batch={})",
            self.store.workspace_id,
            len(entries),
            last_cursor,
            new_cursor,
            len(batch),
        )

        history_text = "\n".join(
            self._format_entry(entry) for entry in batch
        )

        current_memory = await self.store.read_memory() or "(empty)"
        current_soul = await self.store.read_soul() or "(empty)"
        current_user = await self.store.read_user() or "(empty)"

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            history_text=history_text,
            memory=current_memory,
            soul=current_soul,
            user=current_user,
        )

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=None,
                tool_choice=None,
            )
            if response.finish_reason == "error":
                raise RuntimeError(f"LLM returned error: {response.content}")
        except Exception:
            logger.exception("Dream LLM 调用失败 workspace={}", self.store.workspace_id)
            return False

        updates = self._parse_sections(response.content or "")
        applied: list[str] = []
        for doc_type, new_content in updates.items():
            if new_content is None:
                continue
            writer = {
                _DOC_MEMORY: self.store.write_memory,
                _DOC_SOUL: self.store.write_soul,
                _DOC_USER: self.store.write_user,
            }[doc_type]
            await writer(new_content)
            applied.append(doc_type)

        await self.store.set_last_dream_cursor(new_cursor)
        await self.store.compact_history()
        logger.info(
            "Dream: workspace={} 完成，更新文档 {}，cursor→{}",
            self.store.workspace_id,
            applied or "(无)",
            new_cursor,
        )
        return True

    # -- 内部工具 ----------------------------------------------------------

    @staticmethod
    def _format_entry(entry: dict[str, Any]) -> str:
        ts = entry.get("created_at")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%d %H:%M")
        elif isinstance(ts, str):
            ts_str = ts[:16]
        else:
            ts_str = "?"
        return f"[{ts_str}] {entry.get('content', '')}"

    @staticmethod
    def _build_system_prompt() -> str:
        """内联 Dream system prompt，避免单独维护 prompt 文件"""
        return (
            "你是 Dream —— 长期记忆整理器。你需要基于最近的会话 history，"
            "增量更新三份长期记忆文档：MEMORY（客观事实）、SOUL（自身人格）、"
            "USER（用户画像）。\n\n"
            "严格按以下格式输出，不要添加其他说明：\n\n"
            "## NEW_MEMORY\n<完整替换后的 MEMORY 全文；若无需更改请写 NO_CHANGE>\n\n"
            "## NEW_SOUL\n<完整替换后的 SOUL 全文；若无需更改请写 NO_CHANGE>\n\n"
            "## NEW_USER\n<完整替换后的 USER 全文；若无需更改请写 NO_CHANGE>\n\n"
            "规则：\n"
            "1. 输出的是整份文档的新内容，不是 diff。\n"
            "2. 优先做增量补充，不要删除原有重要事实。\n"
            "3. 若 history 对某份文档没有价值，对应段落写 NO_CHANGE 即可。\n"
        )

    @staticmethod
    def _build_user_prompt(
        *,
        history_text: str,
        memory: str,
        soul: str,
        user: str,
    ) -> str:
        return (
            f"## Recent History\n{history_text}\n\n"
            f"## Current MEMORY ({len(memory)} chars)\n{memory}\n\n"
            f"## Current SOUL ({len(soul)} chars)\n{soul}\n\n"
            f"## Current USER ({len(user)} chars)\n{user}\n"
        )

    @classmethod
    def _parse_sections(cls, text: str) -> dict[str, str | None]:
        """把 LLM 输出拆成 {memory, soul, user}；段落是 NO_CHANGE 则值为 None"""
        result: dict[str, str | None] = {
            _DOC_MEMORY: None,
            _DOC_SOUL: None,
            _DOC_USER: None,
        }
        for match in cls._SECTION_RE.finditer(text):
            key = match.group(1).lower()
            raw = match.group(2).strip()
            if not raw or raw.upper() == "NO_CHANGE":
                continue
            result[key] = raw
        return result
