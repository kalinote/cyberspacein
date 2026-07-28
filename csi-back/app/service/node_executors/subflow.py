from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.models.action.node_execution import ActionNodeExecutionModel
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)


class SubflowNodeExecutor:
    """通过嵌入式行动门面启动和跟踪封装节点。"""

    def __init__(
        self,
        start_subflow: Callable[
            [NodeExecutionContext, NodeExecutionSpec],
            Awaitable[str],
        ],
        reconcile_subflow: Callable[
            [str],
            Awaitable[NodeExecutionOutcome | None],
        ],
        cancel_subflow: Callable[[str, str], Awaitable[bool]],
    ):
        self._start_subflow = start_subflow
        self._reconcile_subflow = reconcile_subflow
        self._cancel_subflow = cancel_subflow

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        child_action_id = await self._start_subflow(context, spec)
        return NodeStartResult(
            state="running",
            provider_run_id=child_action_id,
            extension_state={"child_action_id": child_action_id},
        )

    async def reconcile(
        self,
        execution: ActionNodeExecutionModel,
    ) -> NodeExecutionOutcome | None:
        child_action_id = execution.child_action_id or execution.provider_run_id
        if not child_action_id:
            return None
        return await self._reconcile_subflow(child_action_id)

    async def cancel(
        self,
        execution: ActionNodeExecutionModel,
        reason: str,
    ) -> bool:
        child_action_id = execution.child_action_id or execution.provider_run_id
        if not child_action_id:
            return True
        return await self._cancel_subflow(child_action_id, reason)
