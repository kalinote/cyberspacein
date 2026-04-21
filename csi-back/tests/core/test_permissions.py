"""app.core.permissions 权限常量测试。"""

from app.core.permissions import AgentPerms, SystemPerms


def test_system_perms_constants_are_non_empty_strings():
    # 系统权限码应为非空字符串，便于与前后端约定一致
    for name, val in SystemPerms.__dict__.items():
        if not name.isupper():
            continue
        assert isinstance(val, str)
        assert len(val) > 0


def test_system_perms_user_group_permcode_distinct():
    # 典型权限常量应互不相同，避免复制粘贴遗漏
    codes = [
        SystemPerms.USER_VIEW,
        SystemPerms.GROUP_VIEW,
        SystemPerms.PERMCODE_VIEW,
    ]
    assert len(set(codes)) == len(codes)


def test_agent_perms_module_loadable():
    # AgentPerms 占位模块应可导入（后续扩展权限时保持兼容）
    assert AgentPerms is not None
