from app.models.action.node_execution import ActionNodeExecutionModel
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)
from app.service.native_nodes.registry import NativeHandlerRegistry


class BackendNativeNodeExecutor:
    """从可信注册表选择并执行后端原生 Handler。"""

    def __init__(self, handlers: NativeHandlerRegistry):
        self._handlers = handlers

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        return await self._handlers.require(
            spec.handler,
            spec.schema_version,
        ).start(context, spec)

    async def reconcile(
        self,
        execution: ActionNodeExecutionModel,
    ) -> NodeExecutionOutcome | None:
        if not execution.provider_run_id:
            return None
        return await self._handlers.require(
            execution.handler,
            execution.schema_version,
        ).reconcile(
            execution.provider_run_id,
            execution.extension_state,
        )

    async def cancel(
        self,
        execution: ActionNodeExecutionModel,
        reason: str,
    ) -> bool:
        if not execution.provider_run_id:
            return True
        return await self._handlers.require(
            execution.handler,
            execution.schema_version,
        ).cancel(
            execution.provider_run_id,
            reason,
            execution.extension_state,
        )
