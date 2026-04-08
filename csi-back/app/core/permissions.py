class SystemPerms:
    # 系统功能权限
    # 用户管理
    USER_VIEW = "operation:system:permissions:userManagement:users:view"
    USER_CREATE = "operation:system:permissions:userManagement:users:add:use"
    USER_EDIT = "operation:system:permissions:userManagement:users:edit:use"
    USER_DISABLE = "system:user:disable" # TODO: 这里的权限码还需要修改

    GROUP_VIEW = "operation:system:permissions:groupManagement:groups:view"
    GROUP_CREATE = "operation:system:permissions:groupManagement:groups:add:use"
    GROUP_EDIT = "operation:system:permissions:groupManagement:groups:edit:use"

    PERMCODE_VIEW = "operation:system:permissions:dictManagement:dict:view"
    PERMCODE_CREATE = "operation:system:permissions:dictManagement:dict:add:use"
    PERMCODE_EDIT = "operation:system:permissions:dictManagement:dict:edit:use"
    PERMCODE_DELETE = "operation:system:permissions:dictManagement:dict:delete:use"

class AgentPerms:
    # 分析引擎权限
    pass