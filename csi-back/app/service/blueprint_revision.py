from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4
from typing import Any
from pymongo.errors import DuplicateKeyError

from app.models.action.blueprint import (
    ActionBlueprintModel,
    create_blueprint_snapshot,
)
from app.models.action.blueprint_revision import ActionBlueprintRevisionModel
from app.models.action.node import (
    ActionNodeHandleModel,
    ActionNodeInputModel,
    ActionNodeModel,
)
from app.schemas.action.execution import NodeExecutionSpec
from app.schemas.action.interface import BlueprintInterfaceSpec
from app.schemas.constants import (
    DEFAULT_COMPONENT_COMMAND,
    DEFAULT_COMPONENT_COMMAND_ARGS,
    ActionExecutionDriverEnum,
    ActionInvocationModeEnum,
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.service.action.compiler import BlueprintCompiler
from app.service.encapsulated_node import (
    next_encapsulated_definition_version,
    normalize_encapsulated_latest,
)
from app.utils.dict_helper import pack_dict
from app.utils.id_lib import generate_id


class BlueprintRevisionService:
    """发布不可变蓝图Revision并生成封装节点版本。"""

    RUNTIME_CONTRACT_VERSION = 2
    REFERENCE_PROTOCOL_VERSION = "eos-v1"

    @staticmethod
    async def validate(
        blueprint: ActionBlueprintModel,
    ) -> tuple[Any, Any, dict[str, ActionNodeModel]]:
        """同时校验独立运行和封装运行执行图。"""
        definitions = await BlueprintCompiler.load_definitions(blueprint.graph)
        await BlueprintCompiler.hydrate_interface_handle_selections(
            blueprint.graph,
            definitions,
        )
        standalone = BlueprintCompiler.compile(
            blueprint.graph,
            definitions,
            ActionInvocationModeEnum.STANDALONE,
        )
        subflow = BlueprintCompiler.compile(
            blueprint.graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )
        await BlueprintCompiler.validate_encapsulated_dependencies(definitions)
        return standalone, subflow, definitions

    @staticmethod
    async def load_revision_definitions(
        revision: ActionBlueprintRevisionModel,
    ) -> dict[str, ActionNodeModel]:
        """从 Revision 快照恢复节点定义。"""
        definitions = {
            definition_id: ActionNodeModel.model_validate(snapshot)
            for definition_id, snapshot in revision.definition_snapshots.items()
        }
        current_definitions = await ActionNodeModel.find(
            {"_id": {"$in": sorted(definitions)}}
        ).to_list()
        current_by_id = {
            definition.id: definition for definition in current_definitions
        }
        for definition_id, definition in definitions.items():
            if (
                definition.definition_origin
                == ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN
                and (
                    definition_id not in current_by_id
                    or not current_by_id[definition_id].enabled
                )
            ):
                raise ValueError(
                    f"Revision引用的后端原生节点已禁用: {definition.name}"
                )
        return definitions

    @staticmethod
    async def publish(
        blueprint: ActionBlueprintModel,
        *,
        published_by: str | None = None,
    ) -> ActionBlueprintRevisionModel:
        """校验并幂等发布当前蓝图内容。"""
        standalone, subflow, definitions = await BlueprintRevisionService.validate(
            blueprint
        )
        reference_protocol_version = (
            BlueprintRevisionService.REFERENCE_PROTOCOL_VERSION
        )
        runtime_contract_version = BlueprintRevisionService.RUNTIME_CONTRACT_VERSION
        interface = BlueprintInterfaceSpec.model_validate(
            subflow.public_interface_snapshot
        )
        dependencies = sorted(
            {
                definition.source_revision_id
                for definition in definitions.values()
                if definition.node_kind == ActionNodeKindEnum.ENCAPSULATED
                and definition.source_revision_id
            }
        )
        definition_snapshots = {
            definition_id: definition.model_dump(
                mode="python",
                by_alias=True,
            )
            for definition_id, definition in definitions.items()
        }
        definition_content = {
            definition_id: definition.model_dump(
                mode="json",
                by_alias=True,
                exclude={
                    "enabled",
                    "disabled_at",
                    "disabled_by",
                    "is_latest",
                    "is_deleted",
                    "created_at",
                    "updated_at",
                },
            )
            for definition_id, definition in definitions.items()
        }
        content_payload = {
            "runtime_contract_version": runtime_contract_version,
            "reference_protocol_version": reference_protocol_version,
            "blueprint_id": blueprint.id,
            "name": blueprint.name,
            "version": blueprint.version,
            "description": blueprint.description,
            "target": blueprint.target,
            "implementation_period": blueprint.implementation_period,
            "resource": blueprint.resource,
            "graph": blueprint.graph.model_dump(mode="json"),
            "template": blueprint.template,
            "interface": interface.model_dump(mode="json"),
            "dependencies": dependencies,
            "definitions": definition_content,
            "standalone_plan": standalone.model_dump(mode="json"),
            "subflow_plan": subflow.model_dump(mode="json"),
        }
        content_hash = hashlib.sha256(
            json.dumps(
                content_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        existing = await ActionBlueprintRevisionModel.find_one(
            {
                "blueprint_id": blueprint.id,
                "content_hash": content_hash,
                "is_active": True,
            }
        )
        if existing is not None:
            return existing

        latest = await ActionBlueprintRevisionModel.find(
            {"blueprint_id": blueprint.id}
        ).sort("-revision_number").first_or_none()
        revision_number = (latest.revision_number if latest else 0) + 1
        revision_id = generate_id(
            f"blueprint_revision:{blueprint.id}:{revision_number}:{content_hash}"
        )
        execution_specs = {
            node_id: {
                "execution": definition.execution.model_dump(mode="python"),
                "extension": (
                    definition.extension.model_dump(mode="python")
                    if definition.extension
                    else None
                ),
                "definition_version": definition.definition_version,
            }
            for node_id, definition in (
                (
                    node.id,
                    definitions[node.data.definition_id],
                )
                for node in blueprint.graph.nodes
            )
        }
        revision = ActionBlueprintRevisionModel(
            id=revision_id,
            blueprint_id=blueprint.id,
            version=blueprint.version,
            revision_number=revision_number,
            graph_snapshot=blueprint.graph.model_copy(deep=True),
            blueprint_snapshot=create_blueprint_snapshot(blueprint),
            definition_snapshots=definition_snapshots,
            execution_specs_snapshot=execution_specs,
            interface_snapshot=interface,
            template_snapshot=blueprint.template,
            dependency_snapshot=dependencies,
            runtime_contract_version=runtime_contract_version,
            reference_protocol_version=reference_protocol_version,
            content_hash=content_hash,
            published_by=published_by,
        )
        try:
            await revision.insert()
        except DuplicateKeyError:
            concurrent = await ActionBlueprintRevisionModel.find_one(
                {
                    "blueprint_id": blueprint.id,
                    "content_hash": content_hash,
                    "is_active": True,
                }
            )
            if concurrent is not None:
                return concurrent
            return await BlueprintRevisionService.publish(
                blueprint,
                published_by=published_by,
            )
        blueprint.interface = interface
        blueprint.updated_at = datetime.now()
        await blueprint.save()
        return revision

    @staticmethod
    async def encapsulate(
        blueprint: ActionBlueprintModel,
        revision: ActionBlueprintRevisionModel,
        *,
        node_name: str,
        description: str,
        category: str,
        mode: str,
        target_encapsulated_node_id: str | None,
    ) -> ActionNodeModel:
        """创建封装节点资源或为已有资源增加不可变版本。"""
        if mode == "add_version":
            if not target_encapsulated_node_id:
                raise ValueError("增加版本时必须选择已有封装节点")
            target = await ActionNodeModel.find_one(
                {
                    "_id": target_encapsulated_node_id,
                    "definition_origin": ActionNodeDefinitionOriginEnum.BLUEPRINT,
                    "source_blueprint_id": blueprint.id,
                    "is_deleted": False,
                }
            )
            if target is None:
                raise ValueError("目标封装节点不存在或不属于当前蓝图")
            family_id = target.node_family_id or target.id
        else:
            existing_family = await ActionNodeModel.find_one(
                {
                    "source_blueprint_id": blueprint.id,
                    "name": node_name,
                    "node_kind": ActionNodeKindEnum.ENCAPSULATED,
                    "definition_origin": ActionNodeDefinitionOriginEnum.BLUEPRINT,
                    "is_deleted": False,
                }
            )
            if existing_family is not None:
                raise ValueError("当前蓝图已经存在同名封装节点，请选择增加版本")
            family_id = generate_id(
                (
                    f"encapsulated_family:{blueprint.id}:"
                    f"{node_name}:{uuid4().hex}"
                )
            )
        definition_version = await next_encapsulated_definition_version(family_id)

        handles = []
        for port in [
            *revision.interface_snapshot.inputs,
            *revision.interface_snapshot.outputs,
        ]:
            handle_id = f"{port.id}@{revision.id}"
            handles.append(
                ActionNodeHandleModel(
                    id=handle_id,
                    port_id=port.id,
                    handle_config_id=port.handle_config_id,
                    interface_type_id=port.interface_type_id,
                    compatible_interface_type_ids=(
                        port.compatible_interface_type_ids
                    ),
                    relabel=port.name,
                    handle_name=port.name,
                    data_type=port.data_type,
                    label=port.label or port.name,
                    color=port.color or "#0f766e",
                    type="target" if port.direction == "input" else "source",
                    position="left" if port.direction == "input" else "right",
                )
            )

        inputs = []
        if blueprint.is_template and blueprint.template:
            for param in blueprint.template.get("params", []):
                param_id = str(param.get("id") or param.get("name"))
                inputs.append(
                    ActionNodeInputModel(
                        id=param_id,
                        name=param.get("name", param_id),
                        type=param.get("type", "string"),
                        position="center",
                        label=param.get("label", param_id),
                        description=param.get("description") or "",
                        required=bool(param.get("required", False)),
                        default=param.get("default"),
                        options=param.get("options", []),
                        custom_style=[],
                        custom_props=pack_dict(
                            {"validation": param.get("validation", {})}
                        ),
                    )
                )

        node_id = generate_id(
            f"encapsulated_node:{family_id}:{definition_version}"
        )
        node = ActionNodeModel(
            id=node_id,
            name=node_name,
            description=description,
            type=category,
            category=category,
            node_kind=ActionNodeKindEnum.ENCAPSULATED,
            execution=NodeExecutionSpec(
                driver=ActionExecutionDriverEnum.SUBFLOW,
                handler="blueprint.call",
                config={
                    "blueprint_id": blueprint.id,
                    "revision_id": revision.id,
                },
            ),
            extension=None,
            definition_origin=ActionNodeDefinitionOriginEnum.BLUEPRINT,
            node_family_id=family_id,
            definition_version=definition_version,
            enabled=True,
            is_latest=True,
            source_blueprint_id=blueprint.id,
            source_revision_id=revision.id,
            version=str(definition_version),
            handles=handles,
            inputs=inputs,
            default_configs=[],
            related_components=[],
            component_timeouts={},
            command=DEFAULT_COMPONENT_COMMAND,
            command_args=list(DEFAULT_COMPONENT_COMMAND_ARGS),
        )
        await node.insert()
        await normalize_encapsulated_latest(
            family_id,
            preferred_node_id=node.id,
        )
        return node
