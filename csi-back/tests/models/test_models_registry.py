"""app.models 模型注册表 get_all_models 测试。"""

from beanie import Document

from app.models import get_all_models


def test_get_all_models_returns_only_document_subclasses():
    # 注册表中的每一项应为 Beanie Document 子类
    models = get_all_models()
    assert len(models) > 0
    for cls in models:
        assert issubclass(cls, Document)


def test_get_all_models_collection_names_unique():
    # 各模型 Settings.name 应对应不同集合名，避免 Beanie 注册冲突
    models = get_all_models()
    names = [cls.Settings.name for cls in models]
    assert len(names) == len(set(names))


def test_get_all_models_includes_auth_models():
    # 应包含鉴权相关核心模型，便于 init_beanie 一次注册
    from app.models.auth.group import GroupModel
    from app.models.auth.permission_code import PermissionCodeModel
    from app.models.auth.user import UserModel

    models = get_all_models()
    assert UserModel in models
    assert GroupModel in models
    assert PermissionCodeModel in models
