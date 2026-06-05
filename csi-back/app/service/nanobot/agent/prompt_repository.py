"""从 MongoDB 加载并渲染 AGENT 类型内置提示词（Jinja2 字符串模板）。"""

from __future__ import annotations

import platform
import re
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from jinja2 import Environment
from loguru import logger

from app.models.agent.nanobot import NanobotMemoryDocsModel
from app.schemas.constants import NANOBOT_BUILTIN_WORKSPACE_ID, NanobotMemoryDocTypeEnum

logger = logger.bind(name=__name__)

_JINJA_ENV = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)

_DJANGO_COMMENT_RE = re.compile(
    r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}",
    re.DOTALL | re.IGNORECASE,
)


def normalize_jinja_template(template: str) -> str:
    """兼容旧模板中的 Django `{% comment %}` 语法（标准 Jinja2 仅支持 `{# #}`）。"""
    return _DJANGO_COMMENT_RE.sub("", template)


class AgentPromptNotFoundError(LookupError):
    """AGENT 内置提示词文档不存在或不符合约束。"""


def build_builtin_jinja_context(
    *,
    channel: str | None = None,
    platform_policy: str = "",
) -> dict[str, Any]:
    system = platform.system()
    runtime = (
        f"{'macOS' if system == 'Darwin' else system} "
        f"{platform.machine()}, Python {platform.python_version()}"
    )
    return {
        "runtime": runtime,
        "channel": channel or "",
        "system": system,
        "platform_policy": platform_policy,
    }


class AgentPromptRepository:
    """按 id 或 name 读取 workspace_id=__nanobot__ 的 AGENT 文档并渲染。"""

    def __init__(self) -> None:
        self._name_cache: dict[str, str] = {}

    @staticmethod
    def render(template: str, *, strip: bool = False, **kwargs: Any) -> str:
        text = _JINJA_ENV.from_string(normalize_jinja_template(template)).render(**kwargs)
        return text.rstrip() if strip else text

    @staticmethod
    def _id_query(doc_id: str) -> dict[str, Any]:
        try:
            return {"_id": ObjectId(doc_id)}
        except InvalidId:
            return {"_id": doc_id}

    async def _fetch_agent_doc(
        self,
        *,
        doc_id: str | None = None,
        name: str | None = None,
    ) -> NanobotMemoryDocsModel:
        if doc_id is not None:
            doc = await NanobotMemoryDocsModel.find_one(self._id_query(doc_id))
            if doc is None:
                raise AgentPromptNotFoundError(f"AGENT 提示词不存在: id={doc_id}")
        elif name is not None:
            doc = await NanobotMemoryDocsModel.find_one(
                {
                    "workspace_id": NANOBOT_BUILTIN_WORKSPACE_ID,
                    "type": NanobotMemoryDocTypeEnum.AGENT,
                    "name": name,
                }
            )
            if doc is None:
                raise AgentPromptNotFoundError(f"AGENT 提示词不存在: name={name}")
        else:
            raise ValueError("必须提供 doc_id 或 name")

        if doc.type != NanobotMemoryDocTypeEnum.AGENT:
            raise AgentPromptNotFoundError(
                f"文档类型不是 AGENT: id={doc.id} type={doc.type}"
            )
        if doc.workspace_id != NANOBOT_BUILTIN_WORKSPACE_ID:
            raise AgentPromptNotFoundError(
                f"文档 workspace 不是内置域: id={doc.id} workspace_id={doc.workspace_id}"
            )
        return doc

    async def get_content_by_id(self, doc_id: str) -> str:
        doc = await self._fetch_agent_doc(doc_id=doc_id)
        return doc.content

    async def get_content_by_name(self, name: str) -> str:
        if name in self._name_cache:
            return self._name_cache[name]
        doc = await self._fetch_agent_doc(name=name)
        self._name_cache[name] = doc.content
        return doc.content

    async def warm_internal_templates(self) -> None:
        """预加载 name 以 _ 开头的内部模板到进程缓存。"""
        docs = await NanobotMemoryDocsModel.find(
            {
                "workspace_id": NANOBOT_BUILTIN_WORKSPACE_ID,
                "type": NanobotMemoryDocTypeEnum.AGENT,
                "name": {"$regex": r"^_"},
            }
        ).to_list()
        for doc in docs:
            self._name_cache[doc.name] = doc.content

    def render_cached_name(self, name: str, *, strip: bool = False, **kwargs: Any) -> str:
        """同步渲染已缓存的内部模板（须先 warm_internal_templates）。"""
        if name not in self._name_cache:
            raise AgentPromptNotFoundError(f"AGENT 提示词未缓存: name={name}")
        return self.render(self._name_cache[name], strip=strip, **kwargs)

    async def render_by_id(self, doc_id: str, *, strip: bool = False, **kwargs: Any) -> str:
        content = await self.get_content_by_id(doc_id)
        return self.render(content, strip=strip, **kwargs)

    async def render_by_name(self, name: str, *, strip: bool = False, **kwargs: Any) -> str:
        content = await self.get_content_by_name(name)
        return self.render(content, strip=strip, **kwargs)

    @staticmethod
    def _ids_query(doc_ids: list[str]) -> dict[str, Any] | None:
        object_ids: list[ObjectId] = []
        string_ids: list[str] = []
        for doc_id in doc_ids:
            try:
                object_ids.append(ObjectId(doc_id))
            except InvalidId:
                string_ids.append(doc_id)
        or_clauses: list[dict[str, Any]] = []
        if object_ids:
            or_clauses.append({"_id": {"$in": object_ids}})
        if string_ids:
            or_clauses.append({"_id": {"$in": string_ids}})
        if not or_clauses:
            return None
        return {
            "workspace_id": NANOBOT_BUILTIN_WORKSPACE_ID,
            "type": NanobotMemoryDocTypeEnum.AGENT,
            "$or": or_clauses,
        }

    async def fetch_many_by_ids(self, doc_ids: list[str]) -> list[NanobotMemoryDocsModel]:
        if not doc_ids:
            return []
        query = self._ids_query(doc_ids)
        if query is None:
            return []
        docs = await NanobotMemoryDocsModel.find(query).to_list()
        by_id = {str(doc.id): doc for doc in docs}
        ordered: list[NanobotMemoryDocsModel] = []
        for doc_id in doc_ids:
            doc = by_id.get(doc_id)
            if doc is None:
                raise AgentPromptNotFoundError(f"AGENT 提示词不存在: id={doc_id}")
            ordered.append(doc)
        return ordered

    async def resolve_builtin_render_context(
        self,
        doc_ids: list[str],
        *,
        channel: str = "cli",
        skills_summary: str = "",
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        """根据用户选中的内置提示词 id 构建 Jinja 变量；不自动引用未选中的模板。"""
        base = build_builtin_jinja_context(channel=channel)
        if not doc_ids:
            return base
        docs = await self.fetch_many_by_ids(doc_ids)
        combined = "\n".join(doc.content for doc in docs)
        ctx = dict(base)
        policy_doc = next((d for d in docs if d.name == "_platform_policy"), None)
        if policy_doc is not None:
            ctx["platform_policy"] = self.render(policy_doc.content, **base)
        if "skills_summary" in combined and skills_summary:
            ctx["skills_summary"] = skills_summary
        if "max_iterations" in combined and max_iterations is not None:
            ctx["max_iterations"] = max_iterations
        return ctx

    async def render_many_by_ids(
        self,
        doc_ids: list[str],
        *,
        strip: bool = False,
        **kwargs: Any,
    ) -> list[str]:
        if not doc_ids:
            return []
        docs = await self.fetch_many_by_ids(doc_ids)
        return [self.render(doc.content, strip=strip, **kwargs) for doc in docs]
