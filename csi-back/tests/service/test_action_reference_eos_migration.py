from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.migrate_action_reference_eos_v1 import migrate_action_database


class _Cursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, *, length):
        assert length is None
        return self.documents


def _collection(*, count=0, documents=None, external_references=None):
    collection = MagicMock()
    collection.count_documents = AsyncMock(return_value=count)
    collection.find.return_value = _Cursor(documents or [])
    collection.find_one = AsyncMock(
        side_effect=list(external_references or [])
    )
    collection.update_many = AsyncMock(
        return_value=SimpleNamespace(modified_count=count)
    )
    collection.delete_many = AsyncMock(
        return_value=SimpleNamespace(deleted_count=count)
    )
    return collection


@pytest.mark.asyncio
async def test_preview_reports_changes_without_writing():
    action_nodes = _collection(
        count=2,
        documents=[
            {
                "_id": "encapsulated-1",
                "handles": [
                    {
                        "id": "generated-handle",
                        "handle_config_id": "generated-handle",
                    },
                    {
                        "id": "shared-handle",
                        "handle_config_id": "shared-config",
                    },
                ],
            }
        ],
        external_references=[None],
    )
    collections = {
        "action_nodes": action_nodes,
        "reference_bridges": _collection(count=1),
        "component_runs": _collection(count=2),
        "action_node_executions": _collection(count=3),
        "action_instance_nodes": _collection(count=4),
        "action_instances": _collection(count=5),
        "runtime_domain_events": _collection(count=6),
        "action_blueprint_revisions": _collection(count=7),
        "action_nodes_handle_configs": _collection(count=8),
    }
    database = MagicMock()
    database.__getitem__.side_effect = collections.__getitem__

    report = await migrate_action_database(database, apply_changes=False)

    assert report["mode"] == "preview"
    assert report["encapsulated_nodes_to_delete"] == 1
    assert report["orphan_generated_handles_to_delete"] == 1
    assert report["collections_to_clean"]["action_instances"] == 5
    action_nodes.update_many.assert_not_awaited()
    assert all(
        collection.delete_many.await_count == 0
        for collection in collections.values()
    )


@pytest.mark.asyncio
async def test_apply_migrates_nodes_and_cleans_selected_data():
    action_nodes = _collection(
        count=0,
        documents=[
            {
                "_id": "encapsulated-1",
                "handles": [{"id": "generated-handle"}],
            }
        ],
        external_references=[None],
    )
    action_nodes.count_documents = AsyncMock(side_effect=[2, 0])
    action_nodes.update_many.return_value = SimpleNamespace(modified_count=2)
    action_nodes.delete_many.return_value = SimpleNamespace(deleted_count=1)
    collections = {
        "action_nodes": action_nodes,
        "reference_bridges": _collection(count=1),
        "component_runs": _collection(count=1),
        "action_node_executions": _collection(count=1),
        "action_instance_nodes": _collection(count=1),
        "action_instances": _collection(count=1),
        "runtime_domain_events": _collection(count=1),
        "action_blueprint_revisions": _collection(count=1),
        "action_nodes_handle_configs": _collection(count=1),
    }
    database = MagicMock()
    database.__getitem__.side_effect = collections.__getitem__

    report = await migrate_action_database(database, apply_changes=True)

    assert report["ordinary_nodes_migrated"] == 2
    assert report["deleted"]["action_nodes.encapsulated"] == 1
    assert report["deleted"]["action_nodes_handle_configs"] == 1
    action_nodes.update_many.assert_awaited_once()
    collections["action_instances"].delete_many.assert_awaited_once_with({})
    collections["runtime_domain_events"].delete_many.assert_awaited_once_with(
        {"aggregate_type": "action"}
    )
    collections["action_nodes_handle_configs"].delete_many.assert_awaited_once_with(
        {"_id": {"$in": ["generated-handle"]}}
    )


@pytest.mark.asyncio
async def test_apply_stops_before_writes_when_nonordinary_node_is_invalid():
    action_nodes = _collection(count=0)
    action_nodes.count_documents = AsyncMock(side_effect=[1, 1])
    collections = {
        "action_nodes": action_nodes,
        "reference_bridges": _collection(),
        "component_runs": _collection(),
        "action_node_executions": _collection(),
        "action_instance_nodes": _collection(),
        "action_instances": _collection(),
        "runtime_domain_events": _collection(),
        "action_blueprint_revisions": _collection(),
        "action_nodes_handle_configs": _collection(),
    }
    database = MagicMock()
    database.__getitem__.side_effect = collections.__getitem__

    with pytest.raises(RuntimeError, match="node_kind 不是 ordinary"):
        await migrate_action_database(database, apply_changes=True)

    action_nodes.update_many.assert_not_awaited()
    assert all(
        collection.delete_many.await_count == 0
        for collection in collections.values()
    )
