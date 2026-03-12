from datetime import datetime
from pydantic import BaseModel, Field


class SandboxCreateResponse(BaseModel):
    sandbox_id: str = Field(description="沙盒ID（容器短ID）")
    name: str = Field(description="容器名称")
    host_port: int = Field(description="宿主机映射端口")
    status: str = Field(description="容器状态")
    created_at: datetime | None = Field(default=None, description="创建时间")
    image: str = Field(description="镜像名")


class SandboxBaseInfo(BaseModel):
    sandbox_id: str = Field(description="沙盒ID")
    name: str = Field(description="容器名称")
    status: str = Field(description="容器状态")
    image: str = Field(description="镜像名")
    host_port: int | None = Field(default=None, description="宿主机映射端口")
    created_at: datetime | None = Field(default=None, description="创建时间")


class SandboxDetailResponse(BaseModel):
    sandbox_id: str = Field(description="沙盒ID")
    name: str = Field(description="容器名称")
    status: str = Field(description="容器状态")
    image: str = Field(description="镜像名")
    host_port: int | None = Field(default=None, description="宿主机映射端口")
    created_at: datetime | None = Field(default=None, description="创建时间")
    ports: dict = Field(default_factory=dict, description="端口映射详情")
    labels: dict = Field(default_factory=dict, description="容器标签")
