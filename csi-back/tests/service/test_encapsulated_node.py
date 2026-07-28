from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.node import EncapsulatedNodeReferenceResponse
from app.schemas.constants import (
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.service import encapsulated_node as service


class _Query:
    """提供封装节点服务测试所需的最小查询接口。"""

    def __init__(self, values):
        self.values = values
        self.update = AsyncMock()
        self.delete = AsyncMock()

    def sort(self, field):
        reverse = str(field).startswith("-")
        field_name = str(field).removeprefix("-")
        self.values = sorted(
            self.values,
            key=lambda item: getattr(item, field_name),
            reverse=reverse,
        )
        return self

    async def to_list(self):
        """返回当前查询结果。"""
        return self.values

    async def first_or_none(self):
        """返回第一项或空值。"""
        return self.values[0] if self.values else None


def _version(
    version: int,
    *,
    deleted: bool = False,
    latest: bool = False,
) -> SimpleNamespace:
    """构造封装节点版本测试对象。"""
    return SimpleNamespace(
        id=f"node-{version}",
        node_family_id="family-1",
        name="采集子流程",
        description=f"版本 {version}",
        source_blueprint_id="blueprint-source",
        source_revision_id=f"revision-{version}",
        definition_version=version,
        is_deleted=deleted,
        is_latest=latest,
        created_at=datetime(2026, 1, 1) + timedelta(days=version),
        handles=[],
    )


@pytest.mark.asyncio
async def test_family_list_hides_deleted_but_preserves_history_version(
    monkeypatch,
) -> None:
    versions = [
        _version(1),
        _version(2, deleted=True),
        _version(3, latest=True),
    ]
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(lambda _query: _Query(versions)),
    )
    monkeypatch.setattr(
        service,
        "_load_source_blueprints",
        AsyncMock(
            return_value={
                "blueprint-source": SimpleNamespace(
                    id="blueprint-source",
                    name="源蓝图",
                    version="1.0",
                    is_deleted=False,
                )
            }
        ),
    )
    monkeypatch.setattr(
        service,
        "collect_draft_references",
        AsyncMock(
            return_value={
                "node-3": [
                    EncapsulatedNodeReferenceResponse(
                        blueprint_id="parent-1",
                        blueprint_name="父蓝图",
                        blueprint_version="1.0",
                        instance_count=1,
                        instance_ids=["instance-1"],
                    )
                ]
            }
        ),
    )

    result = await service.list_encapsulated_node_families(
        page=1,
        page_size=10,
        keyword="源蓝图",
    )

    assert result.total == 1
    family = result.items[0]
    assert [item.definition_version for item in family.versions] == [3, 1]
    assert family.max_history_version == 3
    assert family.next_definition_version == 4
    assert family.versions[0].draft_reference_count == 1


@pytest.mark.asyncio
async def test_next_version_includes_soft_deleted_tombstone(monkeypatch) -> None:
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(lambda _query: _Query([_version(3, deleted=True)])),
    )

    next_version = await service.next_encapsulated_definition_version("family-1")

    assert next_version == 4


@pytest.mark.asyncio
async def test_delete_rejects_draft_reference(monkeypatch) -> None:
    node = _version(2, latest=True)
    node.update = AsyncMock()
    reference = EncapsulatedNodeReferenceResponse(
        blueprint_id="parent-1",
        blueprint_name="父蓝图",
        blueprint_version="1.0",
        instance_count=1,
        instance_ids=["instance-1"],
    )
    monkeypatch.setattr(
        service,
        "_require_encapsulated_node",
        AsyncMock(return_value=node),
    )
    monkeypatch.setattr(
        service,
        "collect_draft_references",
        AsyncMock(return_value={node.id: [reference]}),
    )

    with pytest.raises(service.EncapsulatedNodeReferencedError) as exc_info:
        await service.delete_encapsulated_node_version(node.id)

    assert exc_info.value.references == [reference]
    node.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_latest_promotes_remaining_version_and_keeps_next_number(
    monkeypatch,
) -> None:
    node = _version(3, latest=True)
    node.update = AsyncMock()
    promoted = _version(1, latest=True)
    clear_cache = AsyncMock()
    monkeypatch.setattr(
        service,
        "_require_encapsulated_node",
        AsyncMock(return_value=node),
    )
    monkeypatch.setattr(
        service,
        "collect_draft_references",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        service,
        "normalize_encapsulated_latest",
        AsyncMock(return_value=promoted),
    )
    monkeypatch.setattr(
        service,
        "next_encapsulated_definition_version",
        AsyncMock(return_value=4),
    )
    monkeypatch.setattr(
        "app.service.action.ActionInstanceService._clear_cache",
        clear_cache,
    )

    result = await service.delete_encapsulated_node_version(node.id)

    deleted_fields = node.update.await_args.args[0]["$set"]
    assert deleted_fields["is_deleted"] is True
    assert deleted_fields["is_latest"] is False
    assert result.promoted_latest_node_id == "node-1"
    assert result.next_definition_version == 4
    assert clear_cache.await_count == 2


@pytest.mark.asyncio
async def test_delete_last_version_physically_removes_family_and_legacy_handles(
    monkeypatch,
) -> None:
    node = _version(3, latest=True)
    node.handles = [
        SimpleNamespace(
            id="legacy-handle@revision-3",
            handle_config_id=None,
        )
    ]
    node.update = AsyncMock()
    family_query = _Query([node])
    handle_query = _Query([])
    clear_cache = AsyncMock()
    monkeypatch.setattr(
        service,
        "_require_encapsulated_node",
        AsyncMock(return_value=node),
    )
    monkeypatch.setattr(
        service,
        "collect_draft_references",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        service,
        "normalize_encapsulated_latest",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(lambda _query: family_query),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find_one",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        ActionNodesHandleConfigModel,
        "find",
        staticmethod(lambda _query: handle_query),
    )
    monkeypatch.setattr(
        "app.service.action.ActionInstanceService._clear_cache",
        clear_cache,
    )

    result = await service.delete_encapsulated_node_version(node.id)

    assert result.family_deleted is True
    assert result.next_definition_version is None
    family_query.delete.assert_awaited_once()
    handle_query.delete.assert_awaited_once()
    assert clear_cache.await_count == 3


@pytest.mark.asyncio
async def test_detail_rejects_non_encapsulated_node(monkeypatch) -> None:
    node = SimpleNamespace(
        node_kind=ActionNodeKindEnum.ORDINARY,
        definition_origin=ActionNodeDefinitionOriginEnum.USER,
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find_one",
        AsyncMock(return_value=node),
    )

    with pytest.raises(TypeError, match="不是蓝图生成"):
        await service.get_encapsulated_node_detail("ordinary-1")
