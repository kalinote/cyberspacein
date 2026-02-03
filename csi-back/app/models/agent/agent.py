from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import Any

class AgentModel(Document):
    id: str = Field(alias="_id")
    name: str = Field(description="Agent名称")
    description: str = Field(description="Agent描述")
    prompt_template_id: str = Field(description="提示词模板id")
    model_id: str = Field(description="模型配置id")
    llm_config: dict[str, Any] = Field(description="LLM配置，包括模型、温度等")
    tools: list[str] = Field(default_factory=list, description="工具列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    class Settings:
        name = "agents"
        indexes = ["name"]
    
class AgentSessionModel(Document):
    thread_id: str = Field(..., description="会话/线程 ID")
    status: str = Field("running", description="running | paused | completed | cancelled")
    fields: dict[str, Any] = Field(default_factory=dict, description="自由字段，用于提示词注入")
    steps: list[dict] = Field(default_factory=list, description="执行步骤，每步含 node、ts 等")
    todos: list[dict] = Field(default_factory=list, description="Todo 项，每项含 content、status")
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())

    class Settings:
        name = "agent_sessions"
        indexes = [
            "thread_id"
        ]
