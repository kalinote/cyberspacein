from beanie import Document
from pydantic import Field
from datetime import datetime

class AgentModel(Document):
    id: str = Field(alias="_id")
    name: str = Field(description="模型名称")
    description: str = Field(description="模型描述")
    prompt_template_id: str = Field(description="提示词模板id")
    llm_config: str = Field(description="LLM配置，包括模型、温度等")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    tools: list[str] = Field(default_factory=list, description="工具列表")
    
    class Settings:
        name = "agents"
        indexes = ["name"]
    
class AgentCheckpointerModel(Document):
    id: str = Field(alias="_id")
    agent_id: str = Field(description="智能体id")
    checkpointer_id: str = Field(description="检查点id")
    data: dict = Field(description="检查点数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    class Settings:
        name = "agent_checkpointers"
        indexes = ["agent_id", "checkpointer_id"]
    
    