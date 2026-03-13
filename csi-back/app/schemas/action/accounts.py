from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.schemas.constants import AccountStatusEnum, RateLimitStrategyEnum

if TYPE_CHECKING:
    from app.models.action.accounts import AccountModel


class CredentialsSchema(BaseModel):
    username: str | None = Field(default=None, description="用户名")
    password: str | None = Field(default=None, description="密码(加密存储)")
    phone: str | None = Field(default=None, description="手机号")
    email: str | None = Field(default=None, description="邮箱")
    two_fa_secret: str | None = Field(default=None, description="2FA密钥")
    extra_fields: dict[str, Any] = Field(default_factory=dict, description="其他登录字段")


class SchedulerSchema(BaseModel):
    is_busy: bool = Field(default=False, description="是否被占用")
    locked_at: datetime | None = Field(default=None, description="锁定时间")
    last_used_at: datetime | None = Field(default=None, description="最近使用时间")
    usage_count_total: int = Field(default=0, description="累计使用次数")
    current_worker_id: str | None = Field(default=None, description="当前占用该账号的节点ID")


class RateLimitSchema(BaseModel):
    strategy: RateLimitStrategyEnum = Field(default=RateLimitStrategyEnum.NONE, description="限制策略")
    max_requests: int = Field(default=0, description="阈值")
    current_usage: int = Field(default=0, description="当前周期内已请求次数")
    reset_at: datetime | None = Field(default=None, description="冷却结束/计数器重置时间")
    cooldown_seconds: int = Field(default=0, description="触发风控后的自定义冷却时长(秒)")


class EnvironmentSchema(BaseModel):
    proxy: str | None = Field(default=None, description="代理ID，空表示不使用代理")
    ua: str | None = Field(default=None, description="固定 User-Agent")
    fingerprint: dict[str, Any] = Field(default_factory=dict, description="浏览器指纹等信息")


class AccountCreateRequest(BaseModel):
    platform_id: str = Field(description="关联平台表ID")
    account_name: str = Field(description="内部展示用的账号别名")
    credentials: CredentialsSchema | None = Field(default=None, description="登录凭证")
    scheduler: SchedulerSchema | None = Field(default=None, description="并发与调度控制")
    rate_limit: RateLimitSchema | None = Field(default=None, description="频率限制")
    environment: EnvironmentSchema | None = Field(default=None, description="环境与指纹绑定")


class AccountUpdateRequest(BaseModel):
    platform_id: str | None = Field(default=None, description="关联平台表ID")
    account_name: str | None = Field(default=None, description="内部展示用的账号别名")
    credentials: CredentialsSchema | None = Field(default=None, description="登录凭证")
    scheduler: SchedulerSchema | None = Field(default=None, description="并发与调度控制")
    rate_limit: RateLimitSchema | None = Field(default=None, description="频率限制")
    environment: EnvironmentSchema | None = Field(default=None, description="环境与指纹绑定")


class AccountResponse(BaseModel):
    id: str = Field(description="账号ID")
    platform_id: str = Field(description="关联平台表ID")
    account_name: str = Field(description="内部展示用的账号别名")
    is_deleted: bool = Field(description="是否已删除(软删除)")
    credentials: CredentialsSchema = Field(description="登录凭证")
    scheduler: SchedulerSchema = Field(description="并发与调度控制")
    rate_limit: RateLimitSchema = Field(description="频率限制")
    environment: EnvironmentSchema = Field(description="环境与指纹绑定")
    status: AccountStatusEnum = Field(description="状态")
    status_reason: str | None = Field(default=None, description="状态描述")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_doc(cls, doc: "AccountModel") -> "AccountResponse":
        return cls(
            id=doc.id,
            platform_id=doc.platform_id,
            account_name=doc.account_name,
            is_deleted=doc.is_deleted,
            credentials=CredentialsSchema.model_validate(doc.credentials.model_dump()),
            scheduler=SchedulerSchema.model_validate(doc.scheduler.model_dump()),
            rate_limit=RateLimitSchema.model_validate(doc.rate_limit.model_dump()),
            environment=EnvironmentSchema.model_validate(doc.environment.model_dump()),
            status=doc.status,
            status_reason=doc.status_reason,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
