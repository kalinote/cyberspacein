"""app.schemas.auth 用户与登录相关 Schema 测试。"""

from datetime import datetime

import pytest

from app.models.auth.user import UserModel
from app.schemas.auth.auth import LoginRequest, LoginResponse
from app.schemas.auth.user import UserCreateRequest, UserResponse, UserUpdateRequest


def test_user_create_request_defaults():
    # 创建用户请求默认值
    r = UserCreateRequest(username="u", password="p", display_name="显示")
    assert r.enabled is True
    assert r.groups == []


def test_user_update_request_all_optional():
    # 更新请求各字段默认均可为空
    u = UserUpdateRequest()
    assert u.display_name is None
    assert u.password is None


def test_login_request_minimal():
    # 登录仅需用户名与密码
    LoginRequest(username="a", password="b")


def test_user_response_from_doc():
    # 从 UserModel 映射到响应 DTO
    doc = UserModel.model_construct(
        id="uid-1",
        username="n",
        display_name="dn",
        password_hash="h",
        create_by="sys",
        create_at=datetime(2024, 1, 1, 12, 0, 0),
        groups=["g1"],
    )
    resp = UserResponse.from_doc(doc)
    assert resp.uuid == "uid-1"
    assert resp.username == "n"
    assert resp.groups == ["g1"]


def test_login_response_structure():
    # 登录响应包含 token 与用户、权限列表
    ur = UserResponse(
        uuid="u",
        create_by="s",
        create_at=datetime.now(),
        update_by=None,
        update_at=None,
        remark=None,
        username="n",
        display_name="d",
        email=None,
        login_ip=None,
        login_date=None,
        enabled=True,
        temporary_account=False,
        expired_at=None,
        groups=[],
    )
    lr = LoginResponse(access_token="tok", user=ur, permissions=["a"])
    assert lr.token_type == "bearer"
    assert lr.permissions == ["a"]
