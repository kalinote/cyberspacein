"""Context builder：基于预取记忆快照拼装 agent prompt。

设计变化：
- `ContextBuilder` 不再直接持有 workspace 目录，也不做文件 I/O。
- 记忆类数据（MEMORY / SOUL / USER / 最近 history）通过 `MemorySnapshot` 一次性
  异步预取（`refresh_memory_snapshot`）后缓存，`build_system_prompt` / `build_messages`
  全部保持**同步接口**，直接读快照。
- `SkillsLoader` 由外部构造并注入（本期只读内置 skills，无 workspace skill）。
- Agent 绑定的 AGENT 内置提示词在装配时预渲染为 `builtin_prompt_sections`；
  未在 `agent_builtin_prompt_ids` 中选中的内置模板不会自动注入 system prompt。
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.service.nanobot.utils.helpers import (
    build_assistant_message,
    current_time_str,
    detect_image_mime,
)

if TYPE_CHECKING:
    from app.service.nanobot.agent.memory import MemoryStore
    from app.service.nanobot.agent.prompt_repository import AgentPromptRepository
    from app.service.nanobot.agent.skills import SkillsLoader


@dataclass
class MemorySnapshot:
    """ContextBuilder 在请求开始时预取的长期记忆快照

    所有字段都是字符串或不可变列表，build_system_prompt 直接读用，不再触发 I/O。
    """

    memory: str = ""
    soul: str = ""
    user: str = ""
    recent_history: list[dict[str, Any]] = field(default_factory=list)


class ContextBuilder:
    """基于 `MemorySnapshot` 拼装 system prompt 与 messages 的同步构造器"""

    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"
    _RUNTIME_CONTEXT_END = "[/Runtime Context]"
    _MAX_RECENT_HISTORY = 50

    def __init__(
        self,
        memory: MemoryStore,
        skills: SkillsLoader | None = None,
        timezone: str | None = None,
        extra_system_suffix: str = "",
        prompt_repo: AgentPromptRepository | None = None,
        builtin_prompt_sections: list[str] | None = None,
    ):
        self.memory = memory
        self.skills = skills
        self.timezone = timezone
        self.prompt_repo = prompt_repo
        self.builtin_prompt_sections: list[str] = list(builtin_prompt_sections or [])
        self.extra_system_suffix: str = extra_system_suffix
        self._snapshot: MemorySnapshot = MemorySnapshot()

    @property
    def snapshot(self) -> MemorySnapshot:
        return self._snapshot

    async def refresh_memory_snapshot(self) -> MemorySnapshot:
        memory_doc, soul_doc, user_doc, dream_cursor = await asyncio.gather(
            self.memory.read_memory(),
            self.memory.read_soul(),
            self.memory.read_user(),
            self.memory.get_last_dream_cursor(),
        )
        entries = await self.memory.read_unprocessed_history(since_cursor=dream_cursor)
        recent = entries[-self._MAX_RECENT_HISTORY:]

        self._snapshot = MemorySnapshot(
            memory=memory_doc,
            soul=soul_doc,
            user=user_doc,
            recent_history=recent,
        )
        return self._snapshot

    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        channel: str | None = None,
    ) -> str:
        snap = self._snapshot
        parts: list[str] = []

        for section in self.builtin_prompt_sections:
            if section and section.strip():
                parts.append(section.strip())

        persona = self._build_persona_block(snap)
        if persona:
            parts.append(persona)

        if snap.memory.strip():
            parts.append(f"# Memory\n\n## Long-term Memory\n{snap.memory}")

        if self.skills is not None:
            always_skills = self.skills.get_always_skills()
            if always_skills:
                always_content = self.skills.load_skills_for_context(always_skills)
                if always_content:
                    parts.append(f"# 激活的 Skills\n\n{always_content}")
        if snap.recent_history:
            parts.append(
                "# Recent History\n\n"
                + "\n".join(
                    f"- [{self._format_history_ts(entry)}] {entry.get('content', '')}"
                    for entry in snap.recent_history
                ),
            )

        if self.extra_system_suffix and self.extra_system_suffix.strip():
            parts.append(self.extra_system_suffix.strip())

        if not parts:
            return ""
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _build_persona_block(snap: MemorySnapshot) -> str:
        pieces: list[str] = []
        if snap.soul.strip():
            pieces.append(f"## SOUL\n\n{snap.soul.rstrip()}")
        if snap.user.strip():
            pieces.append(f"## USER\n\n{snap.user.rstrip()}")
        return "\n\n".join(pieces)

    @staticmethod
    def _format_history_ts(entry: dict[str, Any]) -> str:
        from datetime import datetime as _dt

        ts = entry.get("created_at") or entry.get("timestamp")
        if isinstance(ts, _dt):
            return ts.strftime("%Y-%m-%d %H:%M")
        if isinstance(ts, str) and ts:
            return ts[:16]
        return "?"

    @staticmethod
    def _build_runtime_context(
        channel: str | None,
        chat_id: str | None,
        timezone: str | None = None,
        session_summary: str | None = None,
    ) -> str:
        lines = [f"Current Time: {current_time_str(timezone)}"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        if session_summary:
            lines += ["", "[Resumed Session]", session_summary]
        return (
            ContextBuilder._RUNTIME_CONTEXT_TAG
            + "\n"
            + "\n".join(lines)
            + "\n"
            + ContextBuilder._RUNTIME_CONTEXT_END
        )

    @staticmethod
    def _merge_message_content(left: Any, right: Any) -> str | list[dict[str, Any]]:
        if isinstance(left, str) and isinstance(right, str):
            return f"{left}\n\n{right}" if left else right

        def _to_blocks(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, list):
                return [
                    item if isinstance(item, dict) else {"type": "text", "text": str(item)}
                    for item in value
                ]
            if value is None:
                return []
            return [{"type": "text", "text": str(value)}]

        return _to_blocks(left) + _to_blocks(right)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        current_role: str = "user",
        session_summary: str | None = None,
    ) -> list[dict[str, Any]]:
        runtime_ctx = self._build_runtime_context(
            channel, chat_id, self.timezone, session_summary=session_summary,
        )
        user_content = self._build_user_content(current_message, media)

        if isinstance(user_content, str):
            merged: Any = f"{runtime_ctx}\n\n{user_content}"
        else:
            merged = [{"type": "text", "text": runtime_ctx}] + user_content

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.build_system_prompt(skill_names, channel=channel)},
            *history,
        ]
        if messages[-1].get("role") == current_role:
            last = dict(messages[-1])
            last["content"] = self._merge_message_content(last.get("content"), merged)
            messages[-1] = last
            return messages
        messages.append({"role": current_role, "content": merged})
        return messages

    def _build_user_content(
        self, text: str, media: list[str] | None,
    ) -> str | list[dict[str, Any]]:
        if not media:
            return text

        images: list[dict[str, Any]] = []
        for path in media:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "_meta": {"path": str(p)},
            })

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: Any,
    ) -> list[dict[str, Any]]:
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        return messages

    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        messages.append(build_assistant_message(
            content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        ))
        return messages
