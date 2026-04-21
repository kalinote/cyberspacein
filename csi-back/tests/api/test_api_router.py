"""app.api.v1.api 路由聚合注册测试。"""

from app.api.v1.api import api_router
from app.api.v1.endpoints import auth as auth_ep
from app.api.v1.endpoints import system as system_ep


def test_api_router_has_routes():
    # 聚合路由器应挂载足够多的子路由（业务模块入口）
    assert len(api_router.routes) >= 10


def test_sub_routers_expose_expected_prefix():
    # 认证与系统模块前缀稳定，便于与 api_router 组合
    assert auth_ep.router.prefix == "/auth"
    assert system_ep.router.prefix == "/system"
