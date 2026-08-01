from app.schemas.action.execution import NativeNodeExtensionSpec
from app.service.native_nodes.blueprint_input import BlueprintInputHandler
from app.service.native_nodes.blueprint_output import BlueprintOutputHandler
from app.service.native_nodes.contracts import (
    BackendNativeNodeDefinition,
    NativeHandleDefinition,
    NativeInputDefinition,
)
from app.service.native_nodes.debug_output import DebugOutputNodeHandler
from app.service.native_nodes.entity_content_analysis import (
    EntityContentAnalysisNodeHandler,
)
from app.service.native_nodes.registry import native_definitions, native_handlers

_ENTITY_CONTENT_ANALYSIS_HANDLER = EntityContentAnalysisNodeHandler()
_DEBUG_OUTPUT_HANDLER = DebugOutputNodeHandler()
_INPUT_HANDLER = BlueprintInputHandler()
_OUTPUT_HANDLER = BlueprintOutputHandler()


def register_builtin_native_nodes() -> None:
    """注册首批后端原生节点定义和 Handler。"""
    native_handlers.register(
        "entity.content_analysis",
        _ENTITY_CONTENT_ANALYSIS_HANDLER,
    )
    native_handlers.register("debug.output", _DEBUG_OUTPUT_HANDLER)
    native_handlers.register("blueprint.input", _INPUT_HANDLER)
    native_handlers.register("blueprint.output", _OUTPUT_HANDLER)

    interface_fields = [
        NativeInputDefinition(
            id="interface_name",
            name="interface_name",
            type="string",
            label="接口名称",
            description="封装节点公开 Handle 的显示名称",
            required=True,
            default="",
        ),
        NativeInputDefinition(
            id="public_handle_config_id",
            name="public_handle_config_id",
            type="select",
            label="接口类型",
            description="独立IO节点使用的公开Handle；绑定后自动继承相邻端口",
            required=False,
            default="",
            options=[],
            custom_props={
                "clearable": True,
                "hide_when_boundary_bound": True,
            },
        ),
        NativeInputDefinition(
            id="required",
            name="required",
            type="boolean",
            label="是否必填",
            default=False,
        ),
        NativeInputDefinition(
            id="description",
            name="description",
            type="textarea",
            label="接口说明",
            default="",
        ),
    ]
    native_definitions.register(
        BackendNativeNodeDefinition(
            builtin_key="entity.content_analysis",
            definition_version=1,
            name="实体单例综合内容分析",
            description=(
                "逐条分析完整采集数据，填充翻译、关键词、实体和NSFW字段"
            ),
            handler="entity.content_analysis",
            category="analysis",
            instance_input_schema=[
                NativeInputDefinition(
                    id="model_config_id",
                    name="model_config_id",
                    type="select",
                    label="分析模型",
                    description="直接用于内容分析的模型配置，不依赖分析Agent",
                    required=True,
                    default="",
                    options=[],
                ),
                NativeInputDefinition(
                    id="llm_provider",
                    name="llm_provider",
                    type="select",
                    label="模型协议",
                    description="模型配置所使用的兼容协议",
                    required=True,
                    default="openai",
                    options=[
                        {
                            "label": "OpenAI 兼容",
                            "value": "openai",
                        },
                        {
                            "label": "Anthropic 兼容",
                            "value": "anthropic",
                        },
                    ],
                ),
                NativeInputDefinition(
                    id="analysis_field",
                    name="analysis_field",
                    type="string",
                    label="分析字段",
                    description="要分析的文本字段；留空时使用 clean_content",
                    default="clean_content",
                ),
                NativeInputDefinition(
                    id="min_analysis_length",
                    name="min_analysis_length",
                    type="int",
                    label="最小分析长度",
                    description="文本长度大于该值时才调用模型；留空时使用 50",
                    default=50,
                ),
                NativeInputDefinition(
                    id="chunk_size",
                    name="chunk_size",
                    type="int",
                    label="分块长度",
                    description="正文超过该长度时分块分析；留空时使用 8000",
                    default=8000,
                ),
                NativeInputDefinition(
                    id="user_prompt_override",
                    name="user_prompt_override",
                    type="textarea",
                    label="用户提示词覆盖",
                    description=(
                        "可覆盖默认任务补充提示词；系统安全规则和输出结构保持不变"
                    ),
                    default="",
                ),
                NativeInputDefinition(
                    id="timeout_seconds",
                    name="timeout_seconds",
                    type="int",
                    label="超时秒数",
                    default=1800,
                ),
            ],
            handles=[
                NativeHandleDefinition(
                    port_id="2b1fe999774c1b5edf01040f1c9e2832",
                    interface_type_id="2b1fe999774c1b5edf01040f1c9e2832",
                    handle_name="data_in",
                    direction="target",
                    position="left",
                    data_type="reference",
                    label="数据输入",
                    color="#e6a23c",
                    other_compatible_interfaces=[
                        "2c6d7723c9fc877c56df3a4f14507ede",
                        "74ffd547ab9847640671033b54f13331",
                        "686a4170397bf607448382cc61caa399",
                    ],
                ),
                NativeHandleDefinition(
                    port_id="233ef15e426725c9a26fd7532dd6fdc8",
                    interface_type_id="233ef15e426725c9a26fd7532dd6fdc8",
                    handle_name="dict_in",
                    direction="target",
                    position="left",
                    label="单数据输入",
                    color="#808000",
                    other_compatible_interfaces=[
                        "e878b1c3f9c37cf2bca5faece3647d44",
                    ],
                ),
                NativeHandleDefinition(
                    port_id="74ffd547ab9847640671033b54f13331",
                    interface_type_id="74ffd547ab9847640671033b54f13331",
                    handle_name="data_out",
                    direction="source",
                    position="right",
                    data_type="reference",
                    label="数据输出",
                    color="#e6a23c",
                    other_compatible_interfaces=[
                        "2b1fe999774c1b5edf01040f1c9e2832",
                        "2c6d7723c9fc877c56df3a4f14507ede",
                        "686a4170397bf607448382cc61caa399",
                    ],
                ),
                NativeHandleDefinition(
                    port_id="e878b1c3f9c37cf2bca5faece3647d44",
                    interface_type_id="e878b1c3f9c37cf2bca5faece3647d44",
                    handle_name="dict_out",
                    direction="source",
                    position="right",
                    label="单数据输出",
                    color="#808000",
                    other_compatible_interfaces=[
                        "233ef15e426725c9a26fd7532dd6fdc8",
                    ],
                ),
            ],
            extension=NativeNodeExtensionSpec(
                renderer_key="schema",
            ),
        )
    )
    native_definitions.register(
        BackendNativeNodeDefinition(
            builtin_key="debug.output",
            definition_version=1,
            name="调试输出",
            description="仅在调试运行中观察并记录任意输入数据",
            handler="debug.output",
            category="debug",
            icon="Bug",
            instance_input_schema=[
                NativeInputDefinition(
                    id="debug_output_usage",
                    name="debug_output_usage",
                    type="comment",
                    label="节点说明",
                    description=(
                        "该节点仅在调试运行中启用。可将任意 Value 或 Reference "
                        "输出连接到数据输入，节点会把接收到的每条数据写入行动日志，"
                        "不会修改或继续输出数据。单条日志预览最多展示 24 KiB，普通运行"
                        "会自动跳过该节点。"
                    ),
                )
            ],
            handles=[
                NativeHandleDefinition(
                    port_id="builtin.debug.output.input",
                    interface_type_id="builtin.debug.any",
                    handle_name="data_in",
                    direction="target",
                    position="left",
                    data_type="value",
                    accepted_data_types=["value", "reference"],
                    label="数据输入",
                    color="#64748b",
                    other_compatible_interfaces=["*"],
                )
            ],
            extension=NativeNodeExtensionSpec(
                compiler_adapter="debug.only",
                execution_policy="debug.observer",
                renderer_key="schema",
                config={
                    "compiler": {"allow_multiple_inputs": True},
                    "renderer": {
                        "node_style": {
                            "backgroundColor": "#f1f5f9",
                            "border": "1px solid #94a3b8",
                        }
                    },
                },
            ),
        )
    )
    native_definitions.register(
        BackendNativeNodeDefinition(
            builtin_key="blueprint.input",
            definition_version=1,
            name="蓝图输入",
            description="声明蓝图公开输入；独立运行时由编译器跳过",
            handler="blueprint.input",
            category="io",
            instance_input_schema=interface_fields,
            handles=[
                NativeHandleDefinition(
                    port_id="builtin.blueprint.input.value",
                    interface_type_id="builtin.value",
                    handle_name="blueprint_input",
                    direction="source",
                    position="right",
                    label="蓝图输入",
                    color="#2563eb",
                    other_compatible_interfaces=["*"],
                )
            ],
            extension=NativeNodeExtensionSpec(
                compiler_adapter="blueprint.input",
                renderer_key="schema",
                config={
                    "renderer": {
                        "node_style": {
                            "backgroundColor": "#eff6ff",
                            "border": "1px solid transparent",
                        }
                    }
                },
            ),
        )
    )
    native_definitions.register(
        BackendNativeNodeDefinition(
            builtin_key="blueprint.output",
            definition_version=1,
            name="蓝图输出",
            description="声明蓝图公开输出；独立运行时由编译器跳过",
            handler="blueprint.output",
            category="io",
            instance_input_schema=interface_fields,
            handles=[
                NativeHandleDefinition(
                    port_id="builtin.blueprint.output.value",
                    interface_type_id="builtin.value",
                    handle_name="blueprint_output",
                    direction="target",
                    position="left",
                    label="蓝图输出",
                    color="#7c3aed",
                    other_compatible_interfaces=["*"],
                )
            ],
            extension=NativeNodeExtensionSpec(
                compiler_adapter="blueprint.output",
                renderer_key="schema",
                config={
                    "compiler": {"allow_multiple_inputs": True},
                    "renderer": {
                        "node_style": {
                            "backgroundColor": "#f5f3ff",
                            "border": "1px solid transparent",
                        }
                    },
                },
            ),
        )
    )


async def sync_builtin_native_nodes() -> None:
    """注册并同步内置节点资源投影。"""
    register_builtin_native_nodes()
    await native_definitions.remove_projection(
        builtin_key="analysis",
        definition_version=1,
        handle_ids=[
            "builtin.analysis.input",
            "builtin.analysis.output",
        ],
    )
    await native_definitions.sync_projections()
