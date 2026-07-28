from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.node_execution import ActionNodeExecutionModel
from app.models.agent.runtime import NanobotRunModel
from app.models.runtime_event import RuntimeDomainEventModel
from app.schemas.action.execution import NodeExecutionContext, NodeExecutionSpec
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionInstanceNodeStatusEnum,
    ActionVisibilityEnum,
)
from app.schemas.agent.runtime_state import NanobotRunStatusEnum
from app.service.action import ActionInstanceService
from app.service.analysis_invocation import (
    AnalysisInvocationOutcome,
    AnalysisInvocationRef,
    AnalysisInvocationService,
)
from app.service.native_nodes.analysis import AnalysisNodeHandler
from app.service.runtime_event import RuntimeDomainEventService


class _Query:
    def __init__(self, values):
        self.values = values

    def sort(self, *_args):
        return self

    def limit(self, *_args):
        return self

    async def to_list(self):
        return self.values


@pytest.mark.asyncio
async def test_analysis_handler_starts_action_scoped_run(monkeypatch) -> None:
    submit = AsyncMock(
        return_value=AnalysisInvocationRef(
            agent_id="agent-1",
            session_id="session-1",
            run_id="run-1",
        )
    )
    monkeypatch.setattr(AnalysisInvocationService, "submit", submit)
    handler = AnalysisNodeHandler()

    result = await handler.start(
        NodeExecutionContext(
            action_id="action-1",
            node_instance_id="node-instance-1",
            node_id="analysis-node",
            execution_key="segment-a",
            inputs={"source": "数据", "ignored": "忽略"},
            instance_config={
                "agent_id": "agent-1",
                "input_mapping": {"source": "target"},
                "output_mapping": {"analysis_summary": "summary"},
                "approval_policy": "auto_all",
            },
        ),
        NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler="analysis.invoke",
        ),
    )

    request = submit.await_args.args[0]
    assert request.injection_param == {"target": "数据"}
    assert request.approval_policy == "auto_all"
    assert request.invocation_source == "action_node"
    assert request.source_ref == {
        "action_id": "action-1",
        "node_instance_id": "node-instance-1",
        "execution_key": "segment-a",
    }
    assert result.state == "running"
    assert result.provider_run_id == "run-1"
    assert result.extension_state["output_mapping"] == {
        "analysis_summary": "summary"
    }


@pytest.mark.asyncio
async def test_analysis_handler_maps_approval_and_large_result(monkeypatch) -> None:
    handler = AnalysisNodeHandler()
    ref = {
        "agent_id": "agent-1",
        "session_id": "session-1",
        "run_id": "run-1",
        "output_mapping": {
            "analysis_summary": "summary",
            "analysis_payload": "payload",
            "analysis_result_ref": "result_ref",
        },
    }
    monkeypatch.setattr(
        AnalysisInvocationService,
        "get_outcome",
        AsyncMock(
            return_value=AnalysisInvocationOutcome(
                status="awaiting_approval",
                pending_approval={"id": "approval-1"},
            )
        ),
    )

    approval = await handler.reconcile("run-1", ref)

    assert approval.status == "awaiting_approval"
    assert approval.extension_state["pending_approval"] == {"id": "approval-1"}

    monkeypatch.setattr(
        AnalysisInvocationService,
        "get_outcome",
        AsyncMock(
            return_value=AnalysisInvocationOutcome(
                status="completed",
                result={
                    "summary": "完成",
                    "markdown": "x" * 270_000,
                    "tools_used": ["search"],
                },
            )
        ),
    )

    completed = await handler.reconcile("run-1", ref)

    assert completed.status == "completed"
    assert completed.outputs["summary"] == "完成"
    assert completed.outputs["payload"] is None
    assert completed.outputs["result_ref"] == {
        "session_id": "session-1",
        "run_id": "run-1",
    }
    assert "pending_approval" not in completed.extension_state


@pytest.mark.asyncio
async def test_analysis_terminal_event_is_persistent_and_idempotent(
    monkeypatch,
) -> None:
    inserted = []

    async def insert(event):
        inserted.append(event)

    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )
    monkeypatch.setattr(RuntimeDomainEventModel, "insert", insert)
    run = NanobotRunModel.model_construct(
        id="run-1",
        session_id="session-1",
        agent_id="agent-1",
        workspace_id="workspace-1",
        generation=1,
        user_prompt="分析",
        invocation_source="action_node",
        source_ref={"node_instance_id": "node-instance-1"},
        status=NanobotRunStatusEnum.COMPLETED,
    )

    published = await RuntimeDomainEventService.publish_analysis_run_terminal(run)

    assert published is True
    assert inserted[0].id == "analysis.run.terminal:run-1"
    assert inserted[0].aggregate_id == "run-1"
    assert inserted[0].payload["source_ref"]["node_instance_id"] == "node-instance-1"


@pytest.mark.asyncio
async def test_action_consumes_terminal_event_through_common_reconciler(
    monkeypatch,
) -> None:
    event = SimpleNamespace(
        topic=RuntimeDomainEventService.ANALYSIS_RUN_TERMINAL,
        aggregate_id="run-1",
        payload={"source_ref": {"node_instance_id": "node-instance-1"}},
        update=AsyncMock(),
    )
    execution = SimpleNamespace(
        status=ActionInstanceNodeStatusEnum.RUNNING,
    )
    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "find",
        staticmethod(lambda _query: _Query([event])),
    )
    monkeypatch.setattr(
        ActionNodeExecutionModel,
        "find",
        staticmethod(lambda _query: _Query([execution])),
    )
    reconcile = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "_reconcile_node_execution",
        reconcile,
    )

    consumed = await ActionInstanceService.consume_runtime_events()

    assert consumed == 1
    reconcile.assert_awaited_once_with(execution)
    event.update.assert_awaited_once_with(
        {"$addToSet": {"processed_by": "action-node-executor"}}
    )


@pytest.mark.asyncio
async def test_embedded_action_terminal_event_is_published_and_consumed(
    monkeypatch,
) -> None:
    inserted = []

    async def insert(event):
        inserted.append(event)

    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )
    monkeypatch.setattr(RuntimeDomainEventModel, "insert", insert)
    action = SimpleNamespace(
        id="child-action-1",
        visibility=ActionVisibilityEnum.EMBEDDED,
        parent_action_id="parent-action-1",
        parent_node_instance_id="parent-node-1",
        parent_node_execution_id="parent-execution-1",
    )

    published = await RuntimeDomainEventService.publish_action_terminal(
        action,
        "completed",
    )

    assert published is True
    stored_event = inserted[0]
    assert stored_event.id == "action.terminal:child-action-1"
    assert (
        stored_event.payload["parent_node_execution_id"]
        == "parent-execution-1"
    )

    event = SimpleNamespace(
        topic=stored_event.topic,
        aggregate_id=stored_event.aggregate_id,
        payload=stored_event.payload,
        update=AsyncMock(),
    )
    execution = SimpleNamespace(
        status=ActionInstanceNodeStatusEnum.RUNNING,
    )
    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "find",
        staticmethod(lambda _query: _Query([event])),
    )
    monkeypatch.setattr(
        ActionNodeExecutionModel,
        "find_one",
        AsyncMock(return_value=execution),
    )
    reconcile = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "_reconcile_node_execution",
        reconcile,
    )

    consumed = await ActionInstanceService.consume_runtime_events()

    assert consumed == 1
    reconcile.assert_awaited_once_with(execution)
