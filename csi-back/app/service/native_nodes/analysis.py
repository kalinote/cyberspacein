import json
from typing import Any

from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)
from app.service.analysis_invocation import (
    AnalysisInvocationRef,
    AnalysisInvocationRequest,
    AnalysisInvocationService,
)


class AnalysisNodeHandler:
    """通过统一分析门面启动、对账和取消分析节点。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        config = {**spec.config, **context.instance_config}
        agent_id = str(config.get("agent_id") or "").strip()
        if not agent_id:
            raise ValueError("分析节点必须配置 agent_id")
        prompt = config.get("user_prompt_template")
        input_mapping = config.get("input_mapping") or {}
        if not isinstance(input_mapping, dict):
            raise ValueError("分析节点 input_mapping 必须为键值对象")
        injection_param = {
            str(target): context.inputs.get(source)
            for source, target in input_mapping.items()
            if source in context.inputs
        }
        if not input_mapping:
            injection_param = dict(context.inputs)
        ref = await AnalysisInvocationService.submit(
            AnalysisInvocationRequest(
                agent_id=agent_id,
                user_prompt=prompt,
                injection_param=injection_param,
                merge_user_prompts=bool(config.get("merge_user_prompts", False)),
                auto_approve=bool(config.get("auto_approve", False)),
                approval_policy=config.get("approval_policy", "manual"),
                initiator_user_id=context.initiator_user_id,
                invocation_source="action_node",
                source_ref={
                    "action_id": context.action_id,
                    "node_instance_id": context.node_instance_id,
                    "execution_key": context.execution_key,
                },
            )
        )
        extension_state = ref.model_dump(mode="python")
        output_mapping = config.get("output_mapping") or {}
        if not isinstance(output_mapping, dict):
            raise ValueError("分析节点 output_mapping 必须为键值对象")
        if output_mapping:
            extension_state["output_mapping"] = output_mapping
        return NodeStartResult(
            state="running",
            provider_run_id=ref.run_id or ref.session_id,
            extension_state=extension_state,
        )

    async def reconcile(
        self,
        provider_run_id: str,
        extension_state: dict[str, Any],
    ) -> NodeExecutionOutcome | None:
        ref = AnalysisInvocationRef.model_validate(extension_state)
        outcome = await AnalysisInvocationService.get_outcome(ref)
        if outcome is None:
            return None
        status = "failed" if outcome.status == "interrupted" else outcome.status
        outputs = {}
        extension_state = dict(extension_state)
        if outcome.pending_approval:
            extension_state["pending_approval"] = outcome.pending_approval
        else:
            extension_state.pop("pending_approval", None)
        if outcome.result is not None:
            serialized_size = len(
                json.dumps(
                    outcome.result,
                    ensure_ascii=False,
                    default=str,
                ).encode("utf-8")
            )
            payload = {
                "analysis_session_id": ref.session_id,
                "analysis_run_id": ref.run_id,
                "analysis_success": status == "completed",
                "analysis_summary": outcome.result.get("summary"),
                "analysis_payload": (
                    outcome.result if serialized_size <= 262_144 else None
                ),
                "analysis_markdown": outcome.result.get("markdown"),
                "analysis_tools_used": outcome.result.get("tools_used", []),
                "analysis_result_ref": {
                    "session_id": ref.session_id,
                    "run_id": ref.run_id,
                },
            }
            output_mapping = (
                extension_state.get("output_mapping")
                or {}
            )
            outputs = (
                {
                    str(target): payload.get(source)
                    for source, target in output_mapping.items()
                }
                if output_mapping
                else {"analysis_output": payload}
            )
        return NodeExecutionOutcome(
            status=status,
            outputs=outputs,
            progress=100 if status in {"completed", "failed", "cancelled"} else 0,
            extension_state=extension_state,
            error_message=outcome.error_message,
        )

    async def cancel(
        self,
        provider_run_id: str,
        reason: str,
        extension_state: dict[str, Any],
    ) -> bool:
        return await AnalysisInvocationService.cancel(
            AnalysisInvocationRef.model_validate(extension_state),
            reason,
        )
