"""app.service.action 中与缓存键、序列化相关的轻量测试（不涉及工作流与 DB）。"""

from pydantic import BaseModel

from app.service.action import ActionInstanceService


def test_action_instance_cache_key_format():
    # 缓存键命名空间固定
    assert ActionInstanceService._get_cache_key("blueprint", "bp-1") == "action:cache:blueprint:bp-1"


def test_action_instance_serialize_model_json():
    # 序列化为 JSON 字符串供 Redis 存储
    class M(BaseModel):
        x: int

    s = ActionInstanceService._serialize_model(M(x=1))
    assert '"x":1' in s
