from typing import Any

__all__ = [
    "cancel_component_run",
    "dispatch_component_run",
    "get_components",
    "run_component",
]


def __getattr__(name: str) -> Any:
    """按需导出组件主服务。"""
    if name not in __all__:
        raise AttributeError(f"模块 {__name__!r} 没有属性 {name!r}")
    from app.service.component.service import (
        cancel_component_run,
        dispatch_component_run,
        get_components,
        run_component,
    )

    exports = {
        "cancel_component_run": cancel_component_run,
        "dispatch_component_run": dispatch_component_run,
        "get_components": get_components,
        "run_component": run_component,
    }
    globals().update(exports)
    return exports[name]
