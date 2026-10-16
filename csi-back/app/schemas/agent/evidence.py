"""证据链工具的输入约束；操作只修改图定义，不修改全局实体。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.evidence import (
    EvidenceAnchor,
    EvidenceEntityRef,
    EvidencePosition,
    EvidenceVersionSource,
)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class NewEvidenceNode(EvidenceInput):
    kind: Literal["entity", "note", "collection", "versions"]
    label: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=50)
    position: EvidencePosition = Field(default_factory=EvidencePosition)
    entity: EvidenceEntityRef | None = None
    members: list[EvidenceEntityRef] = Field(default_factory=list, max_length=2000)
    version_source: EvidenceVersionSource | None = None


class EvidenceNodePatch(EvidenceInput):
    label: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    attributes: dict[str, str] | None = Field(default=None, max_length=50)
    entity: EvidenceEntityRef | None = None
    version_source: EvidenceVersionSource | None = None


class EvidenceMetadataPatch(EvidenceInput):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    purpose: str | None = Field(default=None, max_length=500)
    status: Literal["draft", "active", "archived"] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    relation_types: list[str] | None = Field(default=None, max_length=100)


class EvidenceEdgeInput(EvidenceInput):
    source: str = Field(
        min_length=1,
        max_length=2000,
        description="端点 ID 或 $临时名称；支持子链/成员路径",
    )
    target: str = Field(min_length=1, max_length=2000)
    label: str = Field(default="关联", min_length=1, max_length=100)
    directed: bool = True
    description: str = Field(default="", max_length=20000)
    status: Literal["pending", "confirmed", "disputed"] = "pending"
    anchors: list[EvidenceAnchor] = Field(default_factory=list, max_length=100)


class EvidenceEdgePatch(EvidenceInput):
    source: str | None = Field(default=None, min_length=1, max_length=2000)
    target: str | None = Field(default=None, min_length=1, max_length=2000)
    label: str | None = Field(default=None, min_length=1, max_length=100)
    directed: bool | None = None
    description: str | None = Field(default=None, max_length=20000)
    status: Literal["pending", "confirmed", "disputed"] | None = None
    anchors: list[EvidenceAnchor] | None = Field(default=None, max_length=100)


class EvidenceMove(EvidenceInput):
    node_id: str = Field(min_length=1, max_length=101)
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class EvidenceOperation(EvidenceInput):
    op: Literal[
        "set_metadata",
        "add_node",
        "update_node",
        "remove_node",
        "reference_subchain",
        "remove_subchain_reference",
        "add_edge",
        "update_edge",
        "remove_edge",
        "update_collection_members",
        "move_nodes",
        "auto_layout",
    ]
    client_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[\w-]+$",
        description="新增节点/关系的临时名称；同批用 $名称 引用",
    )
    node: NewEvidenceNode | None = None
    node_id: str | None = Field(default=None, min_length=1, max_length=101)
    patch: EvidenceNodePatch | None = None
    metadata: EvidenceMetadataPatch | None = None
    chain_id: str | None = Field(default=None, min_length=1, max_length=100)
    label: str | None = Field(default=None, min_length=1, max_length=300)
    position: EvidencePosition | None = None
    edge: EvidenceEdgeInput | None = None
    edge_id: str | None = Field(default=None, min_length=1, max_length=101)
    edge_patch: EvidenceEdgePatch | None = None
    edge_policy: Literal["reject", "remove_connected"] = "reject"
    members: list[EvidenceEntityRef] | None = Field(default=None, max_length=2000)
    member_mode: Literal["set", "add", "remove"] = "set"
    positions: list[EvidenceMove] | None = Field(
        default=None, min_length=1, max_length=2000
    )
    layout: Literal["grid", "tree"] = "grid"
    node_ids: list[str] | None = Field(default=None, min_length=1, max_length=2000)
    locked_node_ids: list[str] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def validate_operation(self):
        """限制每种操作的字段，防止拼错字段被静默忽略。"""
        required, optional = {
            "set_metadata": ({"metadata"}, set()),
            "add_node": ({"client_key", "node"}, set()),
            "update_node": ({"node_id", "patch"}, set()),
            "remove_node": ({"node_id"}, {"edge_policy"}),
            "reference_subchain": ({"client_key", "chain_id", "label"}, {"position"}),
            "remove_subchain_reference": ({"node_id"}, {"edge_policy"}),
            "add_edge": ({"client_key", "edge"}, set()),
            "update_edge": ({"edge_id", "edge_patch"}, set()),
            "remove_edge": ({"edge_id"}, set()),
            "update_collection_members": (
                {"node_id", "members"},
                {"member_mode", "edge_policy"},
            ),
            "move_nodes": ({"positions"}, set()),
            "auto_layout": (set(), {"layout", "node_ids", "locked_node_ids"}),
        }[self.op]
        missing = {key for key in required if getattr(self, key) is None}
        extra = self.model_fields_set - required - optional - {"op"}
        if missing or extra:
            raise ValueError(
                f"操作 {self.op} 缺少字段 {sorted(missing)}，不适用字段 {sorted(extra)}"
            )
        for key in ("patch", "metadata", "edge_patch"):
            patch = getattr(self, key)
            if patch is not None:
                values = patch.model_dump(exclude_unset=True)
                if not values or any(value is None for value in values.values()):
                    raise ValueError("修改字段不能为空；清空内容请使用空字符串或空列表")
        return self


class EvidenceListInput(EvidenceInput):
    q: str = Field(default="", max_length=200)
    status: Literal["draft", "active", "archived"] | None = None
    tags: list[str] = Field(
        default_factory=list, max_length=30, description="同时匹配所有标签"
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class EvidenceReadInput(EvidenceInput):
    chain_id: str = Field(min_length=1, max_length=100)
    scope: Literal["summary", "graph", "nodes", "edges"] = "graph"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class EvidenceResolveInput(EvidenceInput):
    chain_id: str = Field(min_length=1, max_length=100)
    node_id: str = Field(
        min_length=1, max_length=2000, description="本链节点或子链路径，例如 child/n1"
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)


class EvidenceWriteInput(EvidenceInput):
    reason: str = Field(min_length=1, max_length=4000)
    request_id: str = Field(
        min_length=1,
        max_length=128,
        description="幂等请求标识；同一写入重试必须保持标识和参数不变",
    )


class EvidenceCreateInput(EvidenceWriteInput):
    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=20000)
    template: Literal["blank", "proof", "expansion", "trace"] = "blank"
    tags: list[str] = Field(default_factory=list, max_length=30)


class EvidenceSaveInput(EvidenceWriteInput):
    chain_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1)
    operations: list[EvidenceOperation] = Field(min_length=1, max_length=200)


class EvidenceValidateInput(EvidenceInput):
    chain_id: str = Field(min_length=1, max_length=100)
    expected_revision: int | None = Field(default=None, ge=1)
    operations: list[EvidenceOperation] = Field(default_factory=list, max_length=200)


class EvidenceDeleteInput(EvidenceWriteInput):
    chain_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1)
