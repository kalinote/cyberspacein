from typing import Any

from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)


class BlueprintOutputHandler:
    """把内部上游数据立即映射为子流程公开输出。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        boundary = context.instance_config.get("_compiler", {}).get("boundary", {})
        interface_port_id = boundary.get("interface_port_id")
        grouped_values = [
            value
            for values in context.input_groups.values()
            for value in values
        ]
        output = (
            grouped_values[0]
            if len(grouped_values) == 1
            else grouped_values
        )
        return NodeStartResult(
            state="completed",
            outputs={interface_port_id: output} if interface_port_id else {},
            progress=100,
        )

    async def reconcile(
        self,
        provider_run_id: str,
        extension_state: dict[str, Any],
    ) -> NodeExecutionOutcome | None:
        return None

    async def cancel(
        self,
        provider_run_id: str,
        reason: str,
        extension_state: dict[str, Any],
    ) -> bool:
        return True
