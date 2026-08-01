from __future__ import annotations

from typing import Any

from app.models.action.debug_output_run import (
    DebugOutputInputEdgeModel,
    DebugOutputRunStatusEnum,
)
from app.models.action.node_execution import ActionNodeExecutionModel
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)
from app.service.debug_output_runtime import (
    DebugOutputRuntimeService,
    DebugOutputRuntimeWorker,
)
from app.utils.id_lib import generate_id


class DebugOutputNodeHandler:
    """启动、对账和取消调试输出观察 Run。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        if not context.debug:
            return NodeStartResult(
                state="completed",
                progress=100,
                extension_result={
                    "skipped": True,
                    "reason": "非调试运行",
                },
            )
        incoming_edges, initial_values, initial_aborts = (
            self._normalize_incoming_edges(context)
        )
        execution_id = str(getattr(context, "execution_id", "") or "")
        if not execution_id:
            execution = await ActionNodeExecutionModel.find_one(
                {
                    "action_id": context.action_id,
                    "node_instance_id": context.node_instance_id,
                    "execution_key": context.execution_key,
                }
            )
            if execution is None:
                raise ValueError("调试输出节点缺少对应的执行记录")
            execution_id = execution.id

        run = await DebugOutputRuntimeService.submit(
            action_id=context.action_id,
            node_instance_id=context.node_instance_id,
            node_execution_id=execution_id,
            execution_key=context.execution_key,
            incoming_edges=incoming_edges,
        )
        for edge_id in initial_aborts:
            await DebugOutputRuntimeService.abort_input(
                run.id,
                edge_id,
                "上游输入边在调试观察节点启动前已经中止",
            )
        for edge_id, value in initial_values:
            await DebugOutputRuntimeService.observe_value(
                run.id,
                edge_id,
                value,
            )
        return NodeStartResult(
            state="running",
            provider_run_id=run.id,
            extension_state={"mode": "observer"},
        )

    async def reconcile(
        self,
        provider_run_id: str,
        extension_state: dict[str, Any],
    ) -> NodeExecutionOutcome | None:
        run = await DebugOutputRuntimeService.reconcile(provider_run_id)
        if run is None:
            return NodeExecutionOutcome(
                status="failed",
                extension_state=extension_state,
                error_message="调试输出 Run 不存在",
            )
        ended_count = sum(
            DebugOutputRuntimeWorker._edge_ended(run, edge)
            for edge in run.incoming_edges
        )
        progress = (
            ended_count / len(run.incoming_edges) * 100
            if run.incoming_edges
            else 100
        )
        summary = {
            "logged_count": run.logged_count,
            "logged_byte_count": run.logged_byte_count,
            "truncated_count": run.truncated_count,
            "warning_count": run.warning_count,
            "completed_input_count": ended_count,
            "total_input_count": len(run.incoming_edges),
        }
        if run.status == DebugOutputRunStatusEnum.PENDING:
            return NodeExecutionOutcome(
                status="queued",
                progress=progress,
                extension_state=extension_state,
                extension_result=summary,
            )
        if run.status == DebugOutputRunStatusEnum.RUNNING:
            return NodeExecutionOutcome(
                status="running",
                progress=progress,
                extension_state=extension_state,
                extension_result=summary,
            )
        if run.status == DebugOutputRunStatusEnum.PAUSED:
            return NodeExecutionOutcome(
                status="paused",
                progress=progress,
                extension_state=extension_state,
                extension_result=summary,
                error_message=run.requested_reason,
            )
        if run.status == DebugOutputRunStatusEnum.COMPLETED:
            return NodeExecutionOutcome(
                status="completed",
                progress=100,
                extension_state=extension_state,
                extension_result=summary,
            )
        return NodeExecutionOutcome(
            status=(
                "cancelled"
                if run.status == DebugOutputRunStatusEnum.CANCELLED
                else "failed"
            ),
            progress=100,
            extension_state=extension_state,
            extension_result=summary,
            error_message=run.error_message,
        )

    async def cancel(
        self,
        provider_run_id: str,
        reason: str,
        extension_state: dict[str, Any],
    ) -> bool:
        return await DebugOutputRuntimeService.cancel(provider_run_id, reason)

    @staticmethod
    def _normalize_incoming_edges(
        context: NodeExecutionContext,
    ) -> tuple[
        list[DebugOutputInputEdgeModel],
        list[tuple[str, Any]],
        list[str],
    ]:
        """规范化输入边并提取启动前已交付或中止的 Value。"""
        normalized: list[DebugOutputInputEdgeModel] = []
        initial_values: list[tuple[str, Any]] = []
        initial_aborts: list[str] = []
        for incoming in getattr(context, "incoming_edges", []):
            raw = (
                incoming.model_dump(mode="python")
                if hasattr(incoming, "model_dump")
                else dict(incoming)
            )
            data_type = str(
                getattr(raw.get("data_type"), "value", raw.get("data_type"))
            )
            edge = DebugOutputInputEdgeModel(
                edge_id=str(raw["edge_id"]),
                data_type=data_type,
                source_node_id=str(raw["source_node_id"]),
                source_port_id=str(raw["source_port_id"]),
                target_port_id=str(raw["target_port_id"]),
                value_slot=(
                    str(raw["value_slot"])
                    if raw.get("value_slot") is not None
                    else None
                ),
                reference_stream=raw.get("reference_stream"),
            )
            normalized.append(edge)
            if edge.data_type == "value" and bool(raw.get("aborted")):
                initial_aborts.append(edge.edge_id)
            elif edge.data_type == "value" and bool(
                raw.get("value_available")
            ):
                initial_values.append((edge.edge_id, raw.get("value")))

        if normalized:
            return normalized, initial_values, initial_aborts

        for input_key, streams in context.reference_inputs.items():
            for index, stream in enumerate(streams):
                normalized.append(
                    DebugOutputInputEdgeModel(
                        edge_id=generate_id(
                            f"debug-reference:{context.node_id}:{input_key}:"
                            f"{stream.stream_id}:{index}"
                        ),
                        data_type="reference",
                        source_node_id="unknown",
                        source_port_id=input_key,
                        target_port_id=input_key,
                        reference_stream=stream,
                    )
                )
        return normalized, initial_values, initial_aborts


__all__ = ["DebugOutputNodeHandler"]
