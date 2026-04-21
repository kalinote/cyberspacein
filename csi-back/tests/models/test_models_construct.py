"""Beanie Document 模型字段与 Settings 的构造期行为测试（不连数据库，使用 model_construct）。"""

from datetime import datetime

from app.models.action.action import ActionInstanceModel
from app.models.annotation import AnnotationModel, AnnotationTargetModel, TextOffsetModel
from app.models.auth.group import GroupModel
from app.models.auth.permission_code import PermissionCodeModel
from app.models.auth.user import UserModel
from app.models.platform.platform import PlatformModel
from app.models.search_template import SearchTemplateModel
from app.schemas.constants import (
    AnnotationStyleEnum,
    AnnotationTypeEnum,
    ContentRegionEnum,
)


def test_user_model_settings():
    # UserModel 集合名与索引字段应稳定
    assert UserModel.Settings.name == "auth_users"
    assert "username" in UserModel.Settings.indexes


def test_user_model_minimal_construct():
    # 必填字段通过 model_construct 组装后，默认字段可访问
    u = UserModel.model_construct(
        id="u-1",
        username="n1",
        display_name="显示名",
        password_hash="hash",
    )
    assert u.enabled is True
    assert u.is_deleted is False
    assert u.groups == []


def test_group_model_minimal_construct():
    # 用户组模型默认权限列表为空
    g = GroupModel.model_construct(
        id="g-1",
        group_name="admins",
        display_name="管理员",
    )
    assert g.permissions == []
    assert GroupModel.Settings.name == "auth_groups"


def test_permission_code_model_minimal_construct():
    # 权限码模型分类与标签默认值
    p = PermissionCodeModel.model_construct(
        id="p-1",
        perm_key="operation:demo:view",
        name="演示查看",
        category="demo",
    )
    assert p.tags == []
    assert PermissionCodeModel.Settings.name == "auth_permission_codes"


def test_search_template_model_construct():
    # 检索模板 rules 默认为空 dict
    t = SearchTemplateModel.model_construct(
        id="st-1",
        title="标题",
        description="描述",
        search_query="q",
    )
    assert t.rules == {}
    assert SearchTemplateModel.Settings.name == "search_templates"


def test_platform_model_minimal_construct():
    # 平台模型必填字段与默认列表
    pl = PlatformModel.model_construct(
        id="pl-1",
        name="n",
        description="d",
        type="t",
        net_type="clear",
        status="active",
        url="https://a.com",
        logo="",
        category="c",
        sub_category="s",
    )
    assert pl.tags == []
    assert pl.confidence == 1
    assert PlatformModel.Settings.name == "platforms"


def test_action_instance_model_minimal_construct():
    # 行动实例默认状态与删除标记
    a = ActionInstanceModel.model_construct(id="ai-1", blueprint_id="bp-1")
    assert a.is_deleted is False
    assert a.nodes_id == []
    assert ActionInstanceModel.Settings.name == "action_instances"


def test_annotation_model_nested_fields():
    # 批注模型嵌套 Pydantic 子模型与枚举
    target = AnnotationTargetModel(
        region=ContentRegionEnum.RENDERED,
        text_offset=TextOffsetModel(start=0, end=3, text="abc"),
    )
    ann = AnnotationModel.model_construct(
        id="an-1",
        entity_uuid="e1",
        entity_type="article",
        target=target,
    )
    assert ann.annotation_type == AnnotationTypeEnum.TEXT
    assert ann.style == AnnotationStyleEnum.HIGHLIGHT
    assert isinstance(ann.created_at, datetime)
    assert AnnotationModel.Settings.name == "annotations"
