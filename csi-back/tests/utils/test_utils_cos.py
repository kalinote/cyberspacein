"""app.utils.cos 生命周期与客户端获取测试（不连真实 COS）。"""

import pytest

import app.utils.cos as cos_mod


@pytest.mark.asyncio
async def test_close_cos_clears_session_and_config():
    # 关闭后全局会话与配置应清空
    cos_mod.cos_session = object()
    cos_mod.cos_config = {"k": "v"}
    await cos_mod.close_cos()
    assert cos_mod.cos_session is None
    assert cos_mod.cos_config is None


@pytest.mark.asyncio
async def test_get_cos_client_requires_init():
    # 未初始化时进入上下文管理器应抛错
    cos_mod.cos_session = None
    cos_mod.cos_config = None
    with pytest.raises(RuntimeError, match="未初始化"):
        async with cos_mod.get_cos_client():
            pass
