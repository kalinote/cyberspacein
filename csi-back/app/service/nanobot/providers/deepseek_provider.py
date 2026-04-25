"""DeepSeek 专用 Provider（基于 OpenAI 兼容接口）。"""

from __future__ import annotations

from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider


class DeepSeekProvider(OpenAICompatProvider):
    """DeepSeek 专用 Provider。

    DeepSeek 的 JSON Output 目前仅支持 `response_format={"type":"json_object"}`，
    不支持 `json_schema`。因此这里统一强制使用 `json_object`，避免上层误传导致 400。
    """

    def __init__(self, *args, **kwargs):
        kwargs["response_format"] = {"type": "json_object"}
        super().__init__(*args, **kwargs)

