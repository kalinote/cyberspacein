"""jinja_injection 工具函数测试。"""

from __future__ import annotations

from app.utils.jinja_injection import merge_rendered_user_prompts, render_user_prompt


def test_merge_rendered_user_prompts_order_and_blank_line() -> None:
    merged = merge_rendered_user_prompts("模板段", "请求段")
    assert merged == "模板段\n\n请求段"


def test_render_user_prompt_missing_field_placeholder() -> None:
    rendered = render_user_prompt("你好 {{ k }} {{ missing }}", {"k": "v"})
    assert rendered == "你好 v !字段丢失或不存在!"
