"""app.schemas.auth.group 与 app.schemas.platform 补充测试。"""

from datetime import datetime

import pytest

from app.models.auth.group import GroupModel
from app.schemas.auth.group import GroupCreateRequest, GroupResponse
from app.schemas.platform import PlatformCreateRequestSchema


def test_group_create_request_defaults():
    # 创建用户组默认启用且权限列表为空
    g = GroupCreateRequest(group_name="admins", display_name="管理员")
    assert g.enabled is True
    assert g.permissions == []


def test_group_response_from_doc():
    # 从 GroupModel 映射到响应
    doc = GroupModel.model_construct(
        id="gid",
        group_name="g",
        display_name="显示",
        create_by="sys",
        create_at=datetime(2024, 1, 1, 0, 0, 0),
        permissions=["p1"],
    )
    r = GroupResponse.from_doc(doc)
    assert r.uuid == "gid"
    assert r.permissions == ["p1"]


def test_platform_create_validates_url():
    # URL 非空且可解析
    p = PlatformCreateRequestSchema(
        name="n",
        type="forum",
        url="https://example.com/path",
        category="c",
        sub_category="s",
    )
    assert str(p.url).startswith("https://")


def test_platform_create_rejects_empty_url():
    # 空 URL 应校验失败
    with pytest.raises(Exception):
        PlatformCreateRequestSchema(
            name="n",
            type="t",
            url="",
            category="c",
            sub_category="s",
        )
