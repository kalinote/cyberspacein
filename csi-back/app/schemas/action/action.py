from pydantic import BaseModel, Field

class StartActionRequest(BaseModel):
    blueprint_id: str = Field(description="蓝图ID")
    
class StartActionResponse(BaseModel):
    action_id: str = Field(description="行动ID")