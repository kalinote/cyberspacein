"""app.schemas.auth.permission_code 测试。"""

from datetime import datetime

from app.models.auth.permission_code import PermissionCodeModel
from app.schemas.auth.permission_code import (
    PermissionCodeCreateRequest,
    PermissionCodeResponse,
)


def test_permission_code_create_defaults():
    # 创建请求默认启用且标签为空
    r = PermissionCodeCreateRequest(perm_key="k", name="名称", category="cat")
    assert r.enabled is True
    assert r.tags == []


def test_permission_code_response_from_doc():
    # 从模型映射到响应 DTO
    doc = PermissionCodeModel.model_construct(
        id="pid-1",
        perm_key="operation:x",
        name="名称",
        category="c",
        create_by="sys",
        create_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    resp = PermissionCodeResponse.from_doc(doc)
    assert resp.uuid == "pid-1"
    assert resp.perm_key == "operation:x"
