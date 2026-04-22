"""nanobot 存储协议定义

这些 Protocol 用于解耦 nanobot 内部组件（SessionManager / MemoryStore）与具体存储后端。
csi-back 生产环境只有 MongoDB 实现（见同目录 mongo_*.py），不再保留基于文件系统的版本；
Protocol 仍然保留是为了：
  1. nanobot 内部代码不直接 import `app.models.*`，保持 service 层的边界清晰；
  2. 单元测试中可以注入 in-memory fake。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.service.nanobot.session.manager import Session


@runtime_checkable
class SessionStore(Protocol):
    """会话存储接口，所有方法按 session_id 精确定位

    存量基于 key 字符串的 get_or_create / list_sessions 语义已淘汰：
    - /agent/start 每次生成新 session_id，不做复用；
    - 同一 agent 同时只有一条 running session，由 AnalystService 约束，不落到这里。
    """

    async def load(self, session_id: str) -> "Session | None":
        """按 session_id 加载 Session（含 messages）。不存在返回 None"""
        ...

    async def save(self, session: "Session") -> None:
        """upsert session 元数据；增量 append 新消息（按 seq）

        实现需保证多次调用幂等：已写入的消息不会重复插入。
        """
        ...

    async def list_by_agent(self, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """返回指定 Agent 下的 session 元数据简要列表，按 created_at 倒序，不含 messages"""
        ...

    async def invalidate(self, session_id: str) -> None:
        """内存缓存失效，默认 no-op，仅给分布式缓存场景预留"""
        ...


@runtime_checkable
class MemoryBackend(Protocol):
    """长期记忆 + 历史条目 + 游标状态存储接口，按 workspace_id 隔离

    同一 workspace 下所有 Agent 共享这些数据：
    - MEMORY / SOUL / USER 三类文档：直接读写；
    - history：append-only 的摘要条目，cursor 单调递增；
    - cursors：(last_cursor, last_dream_cursor)。
    """

    # ---- memory docs（MEMORY / SOUL / USER） ----

    async def read_doc(self, workspace_id: str, doc_type: str) -> str:
        """读取指定类型的记忆文档。不存在时返回空字符串

        doc_type 取值对应 NanobotMemoryDocTypeEnum："memory" / "soul" / "user"。
        """
        ...

    async def write_doc(self, workspace_id: str, doc_type: str, content: str) -> None:
        """upsert 指定类型的记忆文档"""
        ...

    # ---- history（append-only 摘要） ----

    async def append_history(self, workspace_id: str, entry: str) -> int:
        """追加一条历史条目，返回本次分配的 cursor（单调递增）

        实现需要原子性分配 cursor，并同步更新 nanobot_history_state.last_cursor。
        """
        ...

    async def read_history(
        self,
        workspace_id: str,
        since_cursor: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """返回 cursor > since_cursor 的历史条目，按 cursor 升序

        返回元素形如 {"cursor": int, "content": str, "created_at": datetime}。
        """
        ...

    async def compact_history(self, workspace_id: str, max_entries: int) -> int:
        """若历史条目数超过 max_entries，按 cursor 升序删除最旧的。返回实际删除条数"""
        ...

    # ---- cursors ----

    async def get_cursors(self, workspace_id: str) -> tuple[int, int]:
        """返回 (last_cursor, last_dream_cursor)。没有记录时返回 (0, 0)"""
        ...

    async def set_dream_cursor(self, workspace_id: str, cursor: int) -> None:
        """更新 last_dream_cursor；last_cursor 由 append_history 内部维护，无需单独设置"""
        ...
