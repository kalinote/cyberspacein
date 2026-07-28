from app.schemas.action.execution import NativeNodeExtensionSpec
from app.service.native_nodes.analysis import AnalysisNodeHandler
from app.service.native_nodes.blueprint_input import BlueprintInputHandler
from app.service.native_nodes.blueprint_output import BlueprintOutputHandler
from app.service.native_nodes.contracts import (
    BackendNativeNodeDefinition,
    NativeHandleDefinition,
    NativeInputDefinition,
)
from app.service.native_nodes.registry import native_definitions, native_handlers

_ANALYSIS_HANDLER = AnalysisNodeHandler()
_INPUT_HANDLER = BlueprintInputHandler()
_OUTPUT_HANDLER = BlueprintOutputHandler()


def register_builtin_native_nodes() -> None:
    """注册首批后端原生节点定义和 Handler。"""
    native_handlers.register("analysis", _ANALYSIS_HANDLER)
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
            custom_props={"clearable": True},
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
            builtin_key="analysis",
            definition_version=1,
            name="分析引擎",
            description="在后端直接运行分析 Agent，不创建 Crawlab 组件任务",
            handler="analysis",
            category="analysis",
            instance_input_schema=[
                NativeInputDefinition(
                    id="agent_id",
                    name="agent_id",
                    type="string",
                    label="分析 Agent",
                    description="要运行的 Agent ID",
                    required=True,
                    default="",
                ),
                NativeInputDefinition(
                    id="user_prompt_template",
                    name="user_prompt_template",
                    type="textarea",
                    label="用户提示词模板",
                    default="",
                ),
                NativeInputDefinition(
                    id="merge_user_prompts",
                    name="merge_user_prompts",
                    type="boolean",
                    label="合并 Agent 默认提示词",
                    default=False,
                ),
                NativeInputDefinition(
                    id="auto_approve",
                    name="auto_approve",
                    type="boolean",
                    label="自动审批写操作",
                    default=False,
                ),
                NativeInputDefinition(
                    id="approval_policy",
                    name="approval_policy",
                    type="select",
                    label="审批策略",
                    description="默认仅对需要审批的写操作进行人工确认",
                    default="manual",
                    options=[
                        {"label": "人工审批", "value": "manual"},
                        {
                            "label": "只读自动执行",
                            "value": "auto_readonly",
                        },
                        {
                            "label": "全部自动审批",
                            "value": "auto_all",
                        },
                    ],
                ),
                NativeInputDefinition(
                    id="input_mapping",
                    name="input_mapping",
                    type="key-value",
                    label="输入映射",
                    description="将上游输入名映射为分析提示词参数名；留空时原样传入",
                    default={},
                ),
                NativeInputDefinition(
                    id="output_mapping",
                    name="output_mapping",
                    type="key-value",
                    label="输出映射",
                    description="将分析结果字段映射为下游输出名；留空时输出完整分析结果",
                    default={},
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
                    port_id="builtin.analysis.input",
                    interface_type_id="builtin.value",
                    handle_name="analysis_input",
                    direction="target",
                    position="left",
                    label="分析输入",
                    color="#d97706",
                ),
                NativeHandleDefinition(
                    port_id="builtin.analysis.output",
                    interface_type_id="builtin.value",
                    handle_name="analysis_output",
                    direction="source",
                    position="right",
                    label="分析结果",
                    color="#d97706",
                ),
            ],
            extension=NativeNodeExtensionSpec(
                renderer_key="analysis",
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
    await native_definitions.sync_projections()
