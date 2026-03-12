from datetime import datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class SandboxModel(Document):
    id: str = Field(alias="_id", description="由 generate_id 生成")
    container_id: str = Field(description="Docker 容器短 ID，即 API 的 sandbox_id")
    container_name: str = Field(description="系统生成的容器名，如 csi-sandbox-8080")
    display_name: str | None = Field(default=None, description="用户设置的显示名，支持中文")
    host_port: int = Field(description="宿主机映射端口")
    image: str = Field(description="创建时使用的镜像")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "sandboxes"
        indexes = [
            "id",
            IndexModel([("container_id", ASCENDING)], unique=True),
            "created_at",
            "display_name",
        ]
