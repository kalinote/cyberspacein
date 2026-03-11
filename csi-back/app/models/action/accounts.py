from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field

from app.schemas.constants import (
    AccountAuthTypeEnum,
    AccountStatusEnum,
    RateLimitStrategyEnum,
)


class CredentialsModel(BaseModel):
    username: str | None = Field(default=None, description="用户名")
    password: str | None = Field(default=None, description="密码(加密存储)")
    phone: str | None = Field(default=None, description="手机号")
    email: str | None = Field(default=None, description="邮箱")
    two_fa_secret: str | None = Field(default=None, description="2FA密钥，用于生成动态验证码")
    extra_fields: dict[str, Any] = Field(default_factory=dict, description="其他登录字段")


class AuthSessionModel(BaseModel):
    auth_type: AccountAuthTypeEnum = Field(description="认证类型: cookie/header/api_key/oauth")
    headers: dict[str, str] = Field(default_factory=dict, description="请求头")
    tokens: dict[str, str] = Field(default_factory=dict, description="access_token/refresh_token/api_key等")
    expired_at: datetime | None = Field(default=None, description="过期时间，null表示永久")
    updated_at: datetime = Field(default_factory=datetime.now, description="认证信息更新时间")


class SchedulerModel(BaseModel):
    is_busy: bool = Field(default=False, description="是否被占用")
    locked_at: datetime | None = Field(default=None, description="锁定时间，可做超时释放")
    last_used_at: datetime | None = Field(default=None, description="最近使用时间")
    usage_count_total: int = Field(default=0, description="累计使用次数")
    current_worker_id: str | None = Field(default=None, description="当前占用该账号的节点ID")


class RateLimitModel(BaseModel):
    strategy: RateLimitStrategyEnum = Field(default=RateLimitStrategyEnum.NONE, description="限制策略，none则不限制")
    max_requests: int = Field(default=0, description="阈值")
    current_usage: int = Field(default=0, description="当前周期内已请求次数")
    reset_at: datetime | None = Field(default=None, description="冷却结束/计数器重置时间")
    cooldown_seconds: int = Field(default=0, description="触发风控后的自定义冷却时长(秒)")


class EnvironmentModel(BaseModel):
    proxy: str | None = Field(default=None, description="代理ID，空表示不使用代理")
    ua: str | None = Field(default=None, description="固定 User-Agent")
    fingerprint: dict[str, Any] = Field(default_factory=dict, description="浏览器指纹等信息")


class AccountModel(Document):
    id: str = Field(alias="_id", description="由 generate_id 生成")
    platform_id: str = Field(description="关联平台表ID")
    account_name: str = Field(description="内部展示用的账号别名")
    is_deleted: bool = Field(default=False, description="是否已删除(软删除)")

    credentials: CredentialsModel = Field(default_factory=CredentialsModel, description="登录凭证")
    auth_session: AuthSessionModel | None = Field(default=None, description="认证状态信息")
    status: AccountStatusEnum = Field(default=AccountStatusEnum.ACTIVE, description="状态")
    status_reason: str | None = Field(default=None, description="状态描述，最后一次失败原因")

    scheduler: SchedulerModel = Field(default_factory=SchedulerModel, description="并发与调度控制")
    rate_limit: RateLimitModel = Field(default_factory=RateLimitModel, description="频率限制")
    environment: EnvironmentModel = Field(default_factory=EnvironmentModel, description="环境与指纹绑定")
    meta: dict[str, Any] = Field(default_factory=dict, description="平台特定元数据")

    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "action_accounts"
        indexes = [
            "id",
            "platform_id",
            "account_name",
            "status",
        ]
