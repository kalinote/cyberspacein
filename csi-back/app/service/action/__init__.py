from typing import Any

__all__ = ["ActionInstanceService", "node_model_to_response"]


def __getattr__(name: str) -> Any:
    """按需导出行动主服务，避免加载子模块时触发循环导入。"""
    if name not in __all__:
        raise AttributeError(f"模块 {__name__!r} 没有属性 {name!r}")
    from app.service.action.service import (
        ActionInstanceService,
        node_model_to_response,
    )

    exports = {
        "ActionInstanceService": ActionInstanceService,
        "node_model_to_response": node_model_to_response,
    }
    globals().update(exports)
    return exports[name]
