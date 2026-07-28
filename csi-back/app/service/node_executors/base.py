from __future__ import annotations

from typing import Protocol

from app.models.action.node_execution import ActionNodeExecutionModel
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)


class NodeExecutor(Protocol):
    """所有一级节点执行器必须实现的协议。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        ...

    async def reconcile(
        self,
        execution: ActionNodeExecutionModel,
    ) -> NodeExecutionOutcome | None:
        ...

    async def cancel(
        self,
        execution: ActionNodeExecutionModel,
        reason: str,
    ) -> bool:
        ...
