from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceEntityRef(BaseModel):
    """指向全局数据对象，不复制正文。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    entity_type: Literal["article", "forum", "wiki"]
    uuid: str = Field(min_length=1, max_length=128, pattern=r"^[\w.:-]+$")


class EvidenceVersionSource(BaseModel):
    """以来源平台和原始数据标识检索全部版本。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    entity_type: Literal["article", "forum"]
    source_id: str = Field(min_length=1, max_length=1024)
    platform: str = Field(min_length=1, max_length=300)


class EvidencePosition(BaseModel):
    x: float = Field(default=0, allow_inf_nan=False)
    y: float = Field(default=0, allow_inf_nan=False)


class EvidenceNode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=100, pattern=r"^[\w-]+$")
    kind: Literal["entity", "note", "collection", "versions", "chain"]
    label: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=50)
    position: EvidencePosition = Field(default_factory=EvidencePosition)
    entity: EvidenceEntityRef | None = None
    members: list[EvidenceEntityRef] = Field(default_factory=list, max_length=2000)
    version_source: EvidenceVersionSource | None = None
    chain_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_payload(self):
        """限制各节点只保存其对应的引用定义。"""
        if (self.kind == "entity") != (self.entity is not None):
            raise ValueError("实体节点必须且只能保存一个实体引用")
        if (self.kind == "versions") != (self.version_source is not None):
            raise ValueError("动态版本节点必须且只能保存来源检索规则")
        if (self.kind == "chain") != bool(self.chain_id):
            raise ValueError("子链节点必须且只能保存证据链引用")
        if self.kind != "collection" and self.members:
            raise ValueError("只有固定集合节点可以保存成员列表")
        if self.kind == "collection" and not self.members:
            raise ValueError("固定集合至少需要一个成员")
        keys = {(ref.entity_type, ref.uuid) for ref in self.members}
        if len(keys) != len(self.members):
            raise ValueError("集合中不能重复引用同一实体")
        if any(len(k) > 100 or len(v) > 4000 for k, v in self.attributes.items()):
            raise ValueError("节点属性名称或内容过长")
        return self


class EvidenceAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    entity: EvidenceEntityRef
    quote: str = Field(default="", max_length=10000)
    locator: str = Field(
        default="", max_length=1000, description="段落、时间点等定位说明"
    )


class EvidenceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=100, pattern=r"^[\w-]+$")
    source: str = Field(min_length=1, max_length=2000)
    target: str = Field(min_length=1, max_length=2000)
    label: str = Field(default="关联", min_length=1, max_length=100)
    directed: bool = True
    description: str = Field(default="", max_length=20000)
    status: Literal["pending", "confirmed", "disputed"] = "pending"
    anchors: list[EvidenceAnchor] = Field(default_factory=list, max_length=100)


class EvidenceGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    purpose: str = Field(default="", max_length=500)
    template: Literal["blank", "proof", "expansion", "trace"] = "blank"
    status: Literal["draft", "active", "archived"] = "draft"
    tags: list[str] = Field(default_factory=list, max_length=30)
    relation_types: list[str] = Field(
        default_factory=lambda: ["关联", "支持", "反驳", "补充", "引用", "先于"],
        max_length=100,
    )
    nodes: list[EvidenceNode] = Field(default_factory=list, max_length=2000)
    edges: list[EvidenceEdge] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_graph(self):
        """校验图的局部身份与端点，不限制普通关系环路。"""
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes) or len({e.id for e in self.edges}) != len(
            self.edges
        ):
            raise ValueError("节点 ID 或关系 ID 重复")
        for edge in self.edges:
            for endpoint in (edge.source, edge.target):
                parts = endpoint.split("/")
                if (
                    parts[0] not in node_ids
                    or any(not p for p in parts)
                    or len(parts) > 33
                ):
                    raise ValueError("关系端点必须属于当前图，嵌套层数不能超过 32")
        if any(not tag or len(tag) > 100 for tag in self.tags + self.relation_types):
            raise ValueError("标签或关系类型不能为空且不能超过 100 字")
        return self


class EvidenceSave(EvidenceGraph):
    expected_revision: int = Field(ge=1)


class EvidenceResolve(BaseModel):
    node: EvidenceNode
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)
