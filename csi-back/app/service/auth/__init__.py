from typing import Any

__all__ = [
    "authenticate_user",
    "bump_group_member_authorization_versions",
    "bump_user_authorization_versions",
    "change_user_credentials",
    "create_user",
    "ensure_default_admin",
    "get_enabled_groups_by_ids",
    "get_user_by_id",
    "get_user_permissions",
    "has_backend_permissions",
    "validate_group_ids",
    "validate_temporary_account",
]


def __getattr__(name: str) -> Any:
    """按需导出认证主服务。"""
    if name not in __all__:
        raise AttributeError(f"模块 {__name__!r} 没有属性 {name!r}")
    from app.service.auth import service

    exports = {export_name: getattr(service, export_name) for export_name in __all__}
    globals().update(exports)
    return exports[name]
