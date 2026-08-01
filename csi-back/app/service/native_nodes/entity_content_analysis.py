from __future__ import annotations

from typing import Any

from app.models.action.entity_content_analysis_run import (
    EntityContentAnalysisRunModeEnum,
    EntityContentAnalysisRunStatusEnum,
)
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)
from app.service.entity_content_analysis_runtime import (
    EntityContentAnalysisRuntimeService,
)

_DATA_IN_PORT_ID = "2b1fe999774c1b5edf01040f1c9e2832"
_DATA_OUT_PORT_ID = "74ffd547ab9847640671033b54f13331"
_DICT_IN_PORT_ID = "233ef15e426725c9a26fd7532dd6fdc8"


class EntityContentAnalysisNodeHandler:
    """启动、对账和取消实体单例综合内容分析 Run。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        config = {**spec.config, **context.instance_config}
        model_config_id = str(config.get("model_config_id") or "").strip()
        if not model_config_id:
            raise ValueError("实体内容分析节点必须选择分析模型")

        llm_provider = str(config.get("llm_provider") or "openai").strip()
        analysis_field = str(
            config.get("analysis_field") or "clean_content"
        ).strip()
        if not analysis_field:
            analysis_field = "clean_content"

        min_analysis_value = config.get("min_analysis_length")
        chunk_size_value = config.get("chunk_size")
        try:
            min_analysis_length = int(
                50
                if min_analysis_value in (None, "")
                else min_analysis_value
            )
            chunk_size = int(
                8000 if chunk_size_value in (None, "") else chunk_size_value
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("最小分析长度和分块长度必须是整数") from exc
        if min_analysis_length < 0:
            raise ValueError("最小分析长度不能小于 0")
        if chunk_size <= 0:
            raise ValueError("分块长度必须大于 0")

        user_prompt_override = str(
            config.get("user_prompt_override") or ""
        ).strip() or None
        single_input: Any = context.inputs.get("dict_in")
        if single_input is None:
            single_input = context.inputs.get(_DICT_IN_PORT_ID)
        if single_input is not None and not isinstance(single_input, dict):
            raise ValueError("单数据输入必须是完整的扁平实体对象")

        source_streams = (
            context.reference_inputs.get("data_in")
            or context.reference_inputs.get(_DATA_IN_PORT_ID)
            or []
        )
        destination_streams = (
            context.reference_outputs.get("data_out")
            or context.reference_outputs.get(_DATA_OUT_PORT_ID)
            or []
        )
        if single_input is not None and source_streams:
            raise ValueError("单数据输入和Reference数据输入不能同时使用")
        if single_input is None and not source_streams:
            raise ValueError("实体内容分析节点未收到任何输入")
        if source_streams and not destination_streams:
            raise ValueError("Reference数据输入必须连接数据输出")

        run = await EntityContentAnalysisRuntimeService.submit(
            action_id=context.action_id,
            node_instance_id=context.node_instance_id,
            execution_key=context.execution_key,
            model_config_id=model_config_id,
            llm_provider=llm_provider,
            single_input=single_input,
            source_streams=source_streams,
            destination_streams=destination_streams,
            analysis_field=analysis_field,
            min_analysis_length=min_analysis_length,
            chunk_size=chunk_size,
            user_prompt_override=user_prompt_override,
        )
        return NodeStartResult(
            state="running",
            provider_run_id=run.id,
            extension_state={"mode": run.mode.value},
        )

    async def reconcile(
        self,
        provider_run_id: str,
        extension_state: dict[str, Any],
    ) -> NodeExecutionOutcome | None:
        run = await EntityContentAnalysisRuntimeService.get(provider_run_id)
        if run is None:
            return NodeExecutionOutcome(
                status="failed",
                extension_state=extension_state,
                error_message="实体内容分析 Run 不存在",
            )

        result_summary = {
            "processed_count": run.processed_count,
            "skipped_count": run.skipped_count,
        }
        if run.status == EntityContentAnalysisRunStatusEnum.PENDING:
            return NodeExecutionOutcome(
                status="queued",
                extension_state=extension_state,
                extension_result=result_summary,
            )
        if run.status == EntityContentAnalysisRunStatusEnum.RUNNING:
            return NodeExecutionOutcome(
                status="running",
                progress=50 if run.mode == EntityContentAnalysisRunModeEnum.SINGLE else 0,
                extension_state=extension_state,
                extension_result=result_summary,
            )
        if run.status == EntityContentAnalysisRunStatusEnum.COMPLETED:
            outputs = (
                {"dict_out": run.single_output}
                if run.mode == EntityContentAnalysisRunModeEnum.SINGLE
                else {}
            )
            return NodeExecutionOutcome(
                status="completed",
                outputs=outputs,
                progress=100,
                extension_state=extension_state,
                extension_result=result_summary,
            )
        return NodeExecutionOutcome(
            status=(
                "cancelled"
                if run.status
                == EntityContentAnalysisRunStatusEnum.CANCELLED
                else "failed"
            ),
            progress=100,
            extension_state=extension_state,
            extension_result=result_summary,
            error_message=run.error_message,
        )

    async def cancel(
        self,
        provider_run_id: str,
        reason: str,
        extension_state: dict[str, Any],
    ) -> bool:
        return await EntityContentAnalysisRuntimeService.cancel(
            provider_run_id,
            reason,
        )
