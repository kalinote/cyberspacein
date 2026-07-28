from typing import Any

from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)


class BlueprintInputHandler:
    """把父流程公开输入立即映射为节点输出。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        boundary = context.instance_config.get("_compiler", {}).get("boundary", {})
        interface_port_id = boundary.get("interface_port_id")
        value = context.invocation_inputs.get(interface_port_id)
        return NodeStartResult(
            state="completed",
            outputs={"blueprint_input": value},
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
