from datetime import datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class LoginSessionModel(Document):
    id: str = Field(alias="_id", description="会话 ID")
    user_id: str = Field(description="用户 ID")
    status: str = Field(default="active", description="active/terminated")
    created_at: datetime = Field(description="创建时间")
    last_activity_at: datetime = Field(description="最后活动时间")
    expires_at: datetime = Field(description="到期时间")
    login_ip: str | None = Field(default=None, description="登录 IP")
    user_agent: str | None = Field(default=None, description="User-Agent")
    credential_version: int = Field(description="登录时凭据版本")
    authorization_version: int = Field(description="登录时授权版本")
    terminated_at: datetime | None = Field(default=None, description="终止时间")
    terminated_reason: str | None = Field(default=None, description="终止原因")

    class Settings:
        name = "auth_login_sessions"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="ix_auth_sessions_user_status"),
            IndexModel([("expires_at", ASCENDING)], name="ix_auth_sessions_expires"),
        ]
