from typing import Optional, List
from pydantic import BaseModel, Field


class LanguageInfo(BaseModel):
    language: str = Field(description="语言名称（如 ENGLISH, CHINESE）")
    iso_code_639_1: Optional[str] = Field(default=None, description="ISO 639-1 代码（如 EN, ZH）")
    iso_code_639_3: Optional[str] = Field(default=None, description="ISO 639-3 代码（如 ENG, ZHO）")


class LanguageDetectRequest(BaseModel):
    text: str = Field(description="要检测的文本内容", min_length=1)


class LanguageDetectResponse(BaseModel):
    result: Optional[LanguageInfo] = Field(default=None, description="检测到的语言信息，如果无法检测则为 None")


class LanguageDetectBatchRequest(BaseModel):
    texts: List[str] = Field(description="要检测的文本列表", min_items=1)


class LanguageDetectBatchResponse(BaseModel):
    results: List[Optional[LanguageInfo]] = Field(description="检测结果列表，与输入文本列表一一对应")


class LanguageConfidenceRequest(BaseModel):
    text: str = Field(description="要计算置信度的文本内容", min_length=1)


class LanguageConfidenceItem(BaseModel):
    language: str = Field(description="语言名称")
    iso_code_639_1: Optional[str] = Field(default=None, description="ISO 639-1 代码")
    iso_code_639_3: Optional[str] = Field(default=None, description="ISO 639-3 代码")
    confidence: float = Field(description="置信度值，范围 0.0-1.0", ge=0.0, le=1.0)


class LanguageConfidenceResponse(BaseModel):
    confidences: List[LanguageConfidenceItem] = Field(description="所有候选语言的置信度列表，按置信度降序排列")


class LanguageDetectMultipleRequest(BaseModel):
    text: str = Field(description="要检测的混合语言文本内容", min_length=1)


class LanguageSegment(BaseModel):
    language: str = Field(description="语言名称")
    iso_code_639_1: Optional[str] = Field(default=None, description="ISO 639-1 代码")
    iso_code_639_3: Optional[str] = Field(default=None, description="ISO 639-3 代码")
    start_index: int = Field(description="文本片段起始位置")
    end_index: int = Field(description="文本片段结束位置")
    text: str = Field(description="检测到的文本片段")


class LanguageDetectMultipleResponse(BaseModel):
    segments: List[LanguageSegment] = Field(description="检测到的不同语言片段列表")
