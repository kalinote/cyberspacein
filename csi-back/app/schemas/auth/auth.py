from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.auth.user import UserResponse


class LoginRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class LoginResponse(BaseModel):
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: UserResponse = Field(description="用户信息")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")
    authorization_version: int = Field(description="当前授权版本")
    session_id: str = Field(description="当前会话 ID")
    session_expires_at: datetime = Field(description="当前会话到期时间")


class CurrentUserResponse(BaseModel):
    user: UserResponse = Field(description="用户信息")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")
    authorization_version: int = Field(description="当前授权版本")
    session_id: str = Field(description="当前会话 ID")
    session_expires_at: datetime = Field(description="当前会话到期时间")
