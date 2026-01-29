from typing import List

from pydantic import BaseModel, Field


class HtmlExtractTextRequest(BaseModel):
    html: str = Field(description="待提取文本的 HTML 内容")


class HtmlExtractTextResponse(BaseModel):
    text: str = Field(description="提取出的纯文本")


class HtmlCleanRequest(BaseModel):
    html: str = Field(description="待清理的 HTML 内容")


class HtmlCleanResponse(BaseModel):
    html: str = Field(description="清理后的 HTML")


class HtmlExtractLinksRequest(BaseModel):
    html: str = Field(description="待提取资源链接的 HTML 内容")


class HtmlExtractLinksResponse(BaseModel):
    links: List[str] = Field(description="提取出的资源链接列表")


class HtmlBatchItem(BaseModel):
    uuid: str = Field(description="本条数据的唯一标识")
    html: str = Field(description="HTML 内容")


class HtmlBatchRequest(BaseModel):
    datas: List[HtmlBatchItem] = Field(description="待处理的数据列表", min_length=1)


class HtmlExtractTextBatchItem(BaseModel):
    uuid: str = Field(description="本条数据的唯一标识")
    text: str = Field(description="提取出的纯文本")


class HtmlCleanBatchItem(BaseModel):
    uuid: str = Field(description="本条数据的唯一标识")
    html: str = Field(description="清理后的 HTML")


class HtmlExtractLinksBatchItem(BaseModel):
    uuid: str = Field(description="本条数据的唯一标识")
    links: List[str] = Field(description="提取出的资源链接列表")
