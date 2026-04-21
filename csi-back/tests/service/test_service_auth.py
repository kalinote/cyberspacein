"""app.service.auth 测试（Beanie 使用 mock，不连真实库）。"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.auth.user import UserCreateRequest
from app.service.auth import (
    authenticate_user,
    create_user,
    get_enabled_groups_by_ids,
    get_user_permissions,
    validate_group_ids,
)


@pytest.mark.asyncio
async def test_get_enabled_groups_by_ids_empty():
    # 空 id 列表直接返回空
    assert await get_enabled_groups_by_ids([]) == []


@pytest.mark.asyncio
async def test_validate_group_ids_empty():
    # 空列表视为无需校验组存在性
    assert await validate_group_ids([]) is True


@pytest.mark.asyncio
async def test_validate_group_ids_all_found(monkeypatch: pytest.MonkeyPatch) -> None:
    # 查询到的组数量与去重后的 id 数量一致则通过
    g1 = MagicMock()
    g2 = MagicMock()

    class FakeQuery:
        async def to_list(self):
            return [g1, g2]

    monkeypatch.setattr(
        "app.service.auth.GroupModel.find",
        lambda *a, **k: FakeQuery(),
    )
    assert await validate_group_ids(["a", "b"]) is True


@pytest.mark.asyncio
async def test_validate_group_ids_missing_group(monkeypatch: pytest.MonkeyPatch) -> None:
    # 请求的组多于查询结果则失败
    class FakeQuery:
        async def to_list(self):
            return [MagicMock()]

    monkeypatch.setattr(
        "app.service.auth.GroupModel.find",
        lambda *a, **k: FakeQuery(),
    )
    assert await validate_group_ids(["a", "b"]) is False


@pytest.mark.asyncio
async def test_get_user_permissions_sorted_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    # 合并多组权限并去重排序
    ga = MagicMock()
    ga.permissions = ["b", "a"]
    gb = MagicMock()
    gb.permissions = ["a", "c"]
    monkeypatch.setattr(
        "app.service.auth.get_enabled_groups_by_ids",
        AsyncMock(return_value=[ga, gb]),
    )
    user = MagicMock()
    user.groups = ["g1", "g2"]
    perms = await get_user_permissions(user)
    assert perms == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_authenticate_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.service.auth.UserModel.find_one",
        AsyncMock(return_value=None),
    )
    assert await authenticate_user("u", "p", None) is None


@pytest.mark.asyncio
async def test_authenticate_user_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    u = MagicMock()
    u.enabled = False
    monkeypatch.setattr(
        "app.service.auth.UserModel.find_one",
        AsyncMock(return_value=u),
    )
    assert await authenticate_user("u", "p", None) is None


@pytest.mark.asyncio
async def test_authenticate_user_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    u = MagicMock()
    u.enabled = True
    u.expired_at = datetime.now() - timedelta(days=1)
    monkeypatch.setattr(
        "app.service.auth.UserModel.find_one",
        AsyncMock(return_value=u),
    )
    assert await authenticate_user("u", "p", None) is None


@pytest.mark.asyncio
async def test_authenticate_user_bad_password(monkeypatch: pytest.MonkeyPatch) -> None:
    u = MagicMock()
    u.enabled = True
    u.expired_at = None
    u.password_hash = "hash"
    monkeypatch.setattr(
        "app.service.auth.UserModel.find_one",
        AsyncMock(return_value=u),
    )
    monkeypatch.setattr("app.service.auth.verify_password", lambda p, h: False)
    assert await authenticate_user("u", "wrong", None) is None


@pytest.mark.asyncio
async def test_authenticate_user_success(monkeypatch: pytest.MonkeyPatch) -> None:
    u = MagicMock()
    u.enabled = True
    u.expired_at = None
    u.password_hash = "hash"
    u.username = "alice"
    u.id = "uid-1"
    u.save = AsyncMock()
    monkeypatch.setattr(
        "app.service.auth.UserModel.find_one",
        AsyncMock(return_value=u),
    )
    monkeypatch.setattr("app.service.auth.verify_password", lambda p, h: True)
    monkeypatch.setattr("app.service.auth.create_access_token", lambda uid: "token-xyz")
    monkeypatch.setattr(
        "app.service.auth.get_user_permissions",
        AsyncMock(return_value=["p1"]),
    )
    out = await authenticate_user("alice", "ok", "127.0.0.1")
    assert out is not None
    token, user, perms = out
    assert token == "token-xyz"
    assert user.id == "uid-1"
    assert perms == ["p1"]
    u.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_duplicate_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.service.auth.UserModel.find_one",
        AsyncMock(return_value=MagicMock()),
    )
    req = UserCreateRequest(username="dup", password="p", display_name="d")
    assert await create_user(req) is None
