"""实体单例综合内容分析原生节点测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.entity_content_analysis_run import (
    EntityContentAnalysisRunModeEnum,
    EntityContentAnalysisRunStatusEnum,
)
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionSpec,
)
from app.schemas.action.reference import ReferenceStreamDescriptor
from app.schemas.constants import ActionExecutionDriverEnum
from app.service.entity_content_analysis_runtime import (
    EntityContentAnalysisRuntimeService,
)
from app.service.native_nodes.definitions import register_builtin_native_nodes
from app.service.native_nodes.entity_content_analysis import (
    EntityContentAnalysisNodeHandler,
)
from app.service.native_nodes.registry import native_definitions, native_handlers


def _spec(config: dict | None = None) -> NodeExecutionSpec:
    """构造实体内容分析节点执行配置。"""
    return NodeExecutionSpec(
        driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
        handler="entity.content_analysis",
        config=config or {},
    )


def _context(
    *,
    inputs: dict | None = None,
    reference_inputs: dict[str, list[ReferenceStreamDescriptor]] | None = None,
    reference_outputs: dict[str, list[ReferenceStreamDescriptor]] | None = None,
    instance_config: dict | None = None,
) -> NodeExecutionContext:
    """构造实体内容分析节点执行上下文。"""
    return NodeExecutionContext(
        action_id="action-1",
        node_instance_id="node-instance-1",
        node_id="analysis-node",
        execution_key="segment-a",
        inputs=inputs or {},
        reference_inputs=reference_inputs or {},
        reference_outputs=reference_outputs or {},
        instance_config=instance_config or {},
    )


def _stream(
    stream_id: str,
    queue_name: str,
    *,
    producer_ids: list[str] | None = None,
) -> ReferenceStreamDescriptor:
    """构造 Reference 流描述符。"""
    return ReferenceStreamDescriptor(
        stream_id=stream_id,
        queue_name=queue_name,
        owner_action_id="action-1",
        expected_producer_ids=producer_ids or [],
    )


def _run(
    *,
    mode: EntityContentAnalysisRunModeEnum,
    status: EntityContentAnalysisRunStatusEnum,
    single_output: dict | None = None,
    error_message: str | None = None,
):
    """构造 Handler 对账使用的运行时结果。"""
    return SimpleNamespace(
        id="run-1",
        mode=mode,
        status=status,
        single_output=single_output,
        processed_count=2,
        skipped_count=1,
        error_message=error_message,
    )


@pytest.mark.asyncio
async def test_single_input_start_submits_default_configuration(
    monkeypatch,
) -> None:
    source = {
        "uuid": "entity-1",
        "entity_type": "article",
        "clean_content": "待分析内容",
    }
    submit = AsyncMock(
        return_value=_run(
            mode=EntityContentAnalysisRunModeEnum.SINGLE,
            status=EntityContentAnalysisRunStatusEnum.PENDING,
        )
    )
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    result = await EntityContentAnalysisNodeHandler().start(
        _context(
            inputs={"dict_in": source},
            instance_config={"model_config_id": "model-1"},
        ),
        _spec(),
    )

    submit.assert_awaited_once_with(
        action_id="action-1",
        node_instance_id="node-instance-1",
        execution_key="segment-a",
        model_config_id="model-1",
        llm_provider="openai",
        single_input=source,
        source_streams=[],
        destination_streams=[],
        analysis_field="clean_content",
        min_analysis_length=50,
        chunk_size=8000,
        user_prompt_override=None,
    )
    assert result.state == "running"
    assert result.provider_run_id == "run-1"
    assert result.extension_state == {"mode": "single"}


@pytest.mark.asyncio
async def test_single_input_start_submits_explicit_configuration(
    monkeypatch,
) -> None:
    submit = AsyncMock(
        return_value=_run(
            mode=EntityContentAnalysisRunModeEnum.SINGLE,
            status=EntityContentAnalysisRunStatusEnum.PENDING,
        )
    )
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    await EntityContentAnalysisNodeHandler().start(
        _context(
            inputs={"dict_in": {"content": "待分析内容"}},
            instance_config={
                "model_config_id": "model-2",
                "llm_provider": "anthropic",
                "analysis_field": "content",
                "min_analysis_length": "12",
                "chunk_size": "4096",
                "user_prompt_override": "  重点识别组织  ",
            },
        ),
        _spec(
            {
                "model_config_id": "default-model",
                "analysis_field": "clean_content",
            }
        ),
    )

    submitted = submit.await_args.kwargs
    assert submitted["model_config_id"] == "model-2"
    assert submitted["llm_provider"] == "anthropic"
    assert submitted["analysis_field"] == "content"
    assert submitted["min_analysis_length"] == 12
    assert submitted["chunk_size"] == 4096
    assert submitted["user_prompt_override"] == "重点识别组织"


@pytest.mark.asyncio
async def test_reference_start_submits_stream_descriptors(monkeypatch) -> None:
    source = _stream(
        "source-stream",
        "source-queue",
        producer_ids=["collector-1"],
    )
    destination = _stream("destination-stream", "destination-queue")
    submit = AsyncMock(
        return_value=_run(
            mode=EntityContentAnalysisRunModeEnum.REFERENCE,
            status=EntityContentAnalysisRunStatusEnum.PENDING,
        )
    )
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    result = await EntityContentAnalysisNodeHandler().start(
        _context(
            reference_inputs={"data_in": [source]},
            reference_outputs={"data_out": [destination]},
            instance_config={"model_config_id": "model-1"},
        ),
        _spec(),
    )

    submitted = submit.await_args.kwargs
    assert submitted["single_input"] is None
    assert submitted["source_streams"] == [source]
    assert submitted["destination_streams"] == [destination]
    assert result.extension_state == {"mode": "reference"}


@pytest.mark.asyncio
async def test_start_rejects_mixed_input_modes(monkeypatch) -> None:
    submit = AsyncMock()
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    with pytest.raises(ValueError, match="不能同时使用"):
        await EntityContentAnalysisNodeHandler().start(
            _context(
                inputs={"dict_in": {"clean_content": "正文"}},
                reference_inputs={
                    "data_in": [_stream("source-stream", "source-queue")]
                },
                reference_outputs={
                    "data_out": [
                        _stream("destination-stream", "destination-queue")
                    ]
                },
                instance_config={"model_config_id": "model-1"},
            ),
            _spec(),
        )

    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reference_start_requires_output_stream(monkeypatch) -> None:
    submit = AsyncMock()
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    with pytest.raises(ValueError, match="必须连接数据输出"):
        await EntityContentAnalysisNodeHandler().start(
            _context(
                reference_inputs={
                    "data_in": [_stream("source-stream", "source-queue")]
                },
                instance_config={"model_config_id": "model-1"},
            ),
            _spec(),
        )

    submit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("inputs", "instance_config", "message"),
    [
        (
            {"dict_in": {"clean_content": "正文"}},
            {},
            "必须选择分析模型",
        ),
        (
            {"dict_in": "正文"},
            {"model_config_id": "model-1"},
            "必须是完整的扁平实体对象",
        ),
        (
            {"dict_in": {"clean_content": "正文"}},
            {
                "model_config_id": "model-1",
                "min_analysis_length": "invalid",
            },
            "必须是整数",
        ),
        (
            {"dict_in": {"clean_content": "正文"}},
            {
                "model_config_id": "model-1",
                "min_analysis_length": -1,
            },
            "不能小于 0",
        ),
        (
            {"dict_in": {"clean_content": "正文"}},
            {
                "model_config_id": "model-1",
                "chunk_size": 0,
            },
            "必须大于 0",
        ),
    ],
)
async def test_start_rejects_invalid_configuration(
    monkeypatch,
    inputs,
    instance_config,
    message,
) -> None:
    submit = AsyncMock()
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    with pytest.raises(ValueError, match=message):
        await EntityContentAnalysisNodeHandler().start(
            _context(
                inputs=inputs,
                instance_config=instance_config,
            ),
            _spec(),
        )

    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_rejects_missing_input(monkeypatch) -> None:
    submit = AsyncMock()
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "submit",
        submit,
    )

    with pytest.raises(ValueError, match="未收到任何输入"):
        await EntityContentAnalysisNodeHandler().start(
            _context(instance_config={"model_config_id": "model-1"}),
            _spec(),
        )

    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_completed_single_returns_dict_output(
    monkeypatch,
) -> None:
    output = {
        "uuid": "entity-1",
        "translate_content": "译文",
        "keywords": ["关键词"],
        "entities": {},
        "nsfw": False,
    }
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "get",
        AsyncMock(
            return_value=_run(
                mode=EntityContentAnalysisRunModeEnum.SINGLE,
                status=EntityContentAnalysisRunStatusEnum.COMPLETED,
                single_output=output,
            )
        ),
    )

    result = await EntityContentAnalysisNodeHandler().reconcile(
        "run-1",
        {"mode": "single"},
    )

    assert result.status == "completed"
    assert result.outputs == {"dict_out": output}
    assert result.progress == 100
    assert result.extension_result == {
        "processed_count": 2,
        "skipped_count": 1,
    }


@pytest.mark.asyncio
async def test_reconcile_completed_reference_has_no_value_output(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "get",
        AsyncMock(
            return_value=_run(
                mode=EntityContentAnalysisRunModeEnum.REFERENCE,
                status=EntityContentAnalysisRunStatusEnum.COMPLETED,
            )
        ),
    )

    result = await EntityContentAnalysisNodeHandler().reconcile(
        "run-1",
        {"mode": "reference"},
    )

    assert result.status == "completed"
    assert result.outputs == {}
    assert result.progress == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("run_status", "outcome_status"),
    [
        (EntityContentAnalysisRunStatusEnum.FAILED, "failed"),
        (EntityContentAnalysisRunStatusEnum.CANCELLED, "cancelled"),
    ],
)
async def test_reconcile_maps_failed_and_cancelled_runs(
    monkeypatch,
    run_status,
    outcome_status,
) -> None:
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "get",
        AsyncMock(
            return_value=_run(
                mode=EntityContentAnalysisRunModeEnum.REFERENCE,
                status=run_status,
                error_message="运行已终止",
            )
        ),
    )

    result = await EntityContentAnalysisNodeHandler().reconcile(
        "run-1",
        {"mode": "reference"},
    )

    assert result.status == outcome_status
    assert result.error_message == "运行已终止"
    assert result.progress == 100


@pytest.mark.asyncio
async def test_cancel_delegates_to_runtime_service(monkeypatch) -> None:
    cancel = AsyncMock(return_value=True)
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "cancel",
        cancel,
    )

    accepted = await EntityContentAnalysisNodeHandler().cancel(
        "run-1",
        "用户停止行动",
        {"mode": "reference"},
    )

    assert accepted is True
    cancel.assert_awaited_once_with("run-1", "用户停止行动")


def test_builtin_registry_contains_only_new_analysis_definition() -> None:
    register_builtin_native_nodes()

    definition = native_definitions.require("entity.content_analysis", 1)
    assert definition.category == "analysis"
    assert definition.handler == "entity.content_analysis"
    assert (
        native_handlers.require("entity.content_analysis", 1).__class__
        is EntityContentAnalysisNodeHandler
    )
    assert {
        handle.handle_name: (
            handle.port_id,
            handle.interface_type_id,
            handle.direction,
            handle.data_type,
        )
        for handle in definition.handles
    } == {
        "data_in": (
            "2b1fe999774c1b5edf01040f1c9e2832",
            "2b1fe999774c1b5edf01040f1c9e2832",
            "target",
            "reference",
        ),
        "dict_in": (
            "233ef15e426725c9a26fd7532dd6fdc8",
            "233ef15e426725c9a26fd7532dd6fdc8",
            "target",
            "value",
        ),
        "data_out": (
            "74ffd547ab9847640671033b54f13331",
            "74ffd547ab9847640671033b54f13331",
            "source",
            "reference",
        ),
        "dict_out": (
            "e878b1c3f9c37cf2bca5faece3647d44",
            "e878b1c3f9c37cf2bca5faece3647d44",
            "source",
            "value",
        ),
    }
    assert all(
        item.builtin_key != "analysis"
        for item in native_definitions.all()
    )
    with pytest.raises(ValueError, match="定义未注册"):
        native_definitions.require("analysis")
