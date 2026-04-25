from __future__ import annotations

import re
from typing import Any

from jinja2 import Environment, Undefined


_MISSING_VALUE_PLACEHOLDER = "!字段丢失或不存在!"
_VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _MissingFieldUndefined(Undefined):
    def __str__(self) -> str:  # pragma: no cover - jinja2 内部调用路径多样
        return _MISSING_VALUE_PLACEHOLDER

    def __repr__(self) -> str:  # pragma: no cover
        return _MISSING_VALUE_PLACEHOLDER

    def __getattr__(self, name: str) -> "_MissingFieldUndefined":  # pragma: no cover
        return self

    def __getitem__(self, key: Any) -> "_MissingFieldUndefined":  # pragma: no cover
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> "_MissingFieldUndefined":  # pragma: no cover
        return self


_ENV = Environment(autoescape=False, undefined=_MissingFieldUndefined)


def render_user_prompt(template_text: str, context: dict[str, Any] | None) -> str:
    """对 user_prompt 做 Jinja2 渲染注入。

    - 缺失字段统一替换为 `!字段丢失或不存在!`
    - 始终注入一个 `ctx` 变量，便于访问非标识符 key：`{{ ctx['a-b'] }}`
    - 同时把符合标识符规范的 key 平铺到顶层：`{{ entity_uuid }}` 这种更方便
    """
    ctx = dict(context or {})
    top_level: dict[str, Any] = {"ctx": ctx}
    for k, v in ctx.items():
        if isinstance(k, str) and _VALID_IDENTIFIER.match(k):
            top_level[k] = v
    return _ENV.from_string(template_text or "").render(**top_level)


__all__ = ["render_user_prompt"]
