from datetime import datetime
from beanie import Document
from pydantic import Field

from app.schemas.constants import NanobotMessageRoleEnum

class NanobotConfigModel(Document):
    """Agent全局配置"""
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    # TODO: 具体数据格式还需要进一步优化，利用模型表和提示词表
    data: dict = Field(default_factory=dict, description="具体配置数据")
    
    class Settings:
        name = "nanobot_configs"
        indexes = [
            "id",
            "create_at",
            "update_at",
        ]

class NanobotSessionModel(Document):
    """会话元数据，每个会话一个文档"""
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    config_id: str = Field(description="配置ID")
    metadata: dict = Field(default_factory=dict, description="会话元数据")
    last_consolidated_seq: int = Field(default=0, description="消息序号序列")
    
    class Settings:
        name = "nanobot_sessions"
        indexes = [
            "id",
            "create_at",
            "update_at",
        ]

class NanobotSessionMessagesModel(Document):
    """消息事件流，每个会话多条消息文档"""
    id: str = Field(alias="_id")
    session_id: str = Field(description="会话ID")
    seq: int = Field(description="消息序号，递增")
    role: NanobotMessageRoleEnum = Field(description="消息角色")
    content: str = Field(description="消息内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    
    # subagent 后续需要考虑是否优化 sender_id，目前应该不需要多用户支持
    sender_id: str = Field(description="发送者ID，用于区分普通用户和Subagent")
    injected_event: str = Field(description="注入事件")
    subagent_task_id: str = Field(description="子代理任务ID")

    # assistant only
    tool_calls: list[dict] = Field(default_factory=list, description="工具调用列表，当消息role为assistant时，该字段为assistant需要调用的工具列表")
    reasoning_content: str = Field(description="推理内容，一般来说这个推理内容不需要放到上下文中")
    
    # anthropic only
    thinking_blocks: list[dict] = Field(default_factory=list, description="思考块列表，当消息role为assistant时，该字段为assistant的思考块列表")

    # tool only
    tool_call_id: str = Field(description="工具调用消息ID，当消息role为tool时，该字段为工具调用实例ID")
    tool_call_name: str = Field(description="工具名称，当消息role为tool时，该字段为工具名称")
