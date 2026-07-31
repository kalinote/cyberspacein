"""行动节点动态选项服务。"""

from collections.abc import Collection
from typing import Literal

from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.configs import ActionHandleOptionResponse
from app.schemas.action.node import ActionNodeOption, ActionNodeResponse

HandleDirection = Literal["source", "target"]


async def collect_node_handle_options(
    directions: Collection[HandleDirection],
) -> dict[HandleDirection, list[ActionHandleOptionResponse]]:
    """聚合指定方向可供蓝图 IO 节点公开的 Handle 配置。

    Args:
        directions: 需要聚合的节点端口方向。

    Returns:
        按端口方向分组的有效 Handle 候选项。
    """
    requested_directions = set(directions)
    results: dict[HandleDirection, list[ActionHandleOptionResponse]] = {
        direction: [] for direction in requested_directions
    }
    if not requested_directions:
        return results

    nodes = await ActionNodeModel.find(
        {
            "is_deleted": False,
            "enabled": True,
            "node_kind": {"$ne": "encapsulated"},
        }
    ).to_list()
    usages: dict[
        HandleDirection,
        dict[str, list],
    ] = {direction: {} for direction in requested_directions}
    for node in nodes:
        if node.builtin_key in {"blueprint.input", "blueprint.output"}:
            continue
        for handle in node.handles:
            if handle.type not in requested_directions:
                continue
            config_id = handle.handle_config_id or handle.id
            usages[handle.type].setdefault(config_id, []).append(handle)

    config_ids = sorted(
        {
            config_id
            for direction_usages in usages.values()
            for config_id in direction_usages
        }
    )
    if not config_ids:
        return results

    configs = await ActionNodesHandleConfigModel.find(
        {"_id": {"$in": config_ids}}
    ).to_list()
    for config in sorted(configs, key=lambda item: (item.label, item.id)):
        for direction, direction_usages in usages.items():
            handles = direction_usages.get(config.id)
            if not handles:
                continue
            interface_types = {
                handle.interface_type_id or config.id for handle in handles
            }
            if len(interface_types) != 1:
                continue
            compatible = {
                *config.other_compatible_interfaces,
                *(
                    interface_id
                    for handle in handles
                    for interface_id in handle.compatible_interface_type_ids
                ),
            }
            results[direction].append(
                ActionHandleOptionResponse(
                    id=config.id,
                    handle_name=config.handle_name,
                    label=config.label,
                    direction=direction,
                    data_type=config.type,
                    interface_type_id=next(iter(interface_types)),
                    compatible_interface_type_ids=sorted(compatible),
                    color=config.color,
                )
            )
    return results


def apply_blueprint_io_handle_options(
    nodes: list[ActionNodeResponse],
    options_by_direction: dict[
        HandleDirection,
        list[ActionHandleOptionResponse],
    ],
) -> None:
    """把动态 Handle 候选项写入蓝图 IO 节点的既有输入 Schema。

    Args:
        nodes: 待补全动态选项的节点响应。
        options_by_direction: 按普通节点端口方向分组的候选项。
    """
    direction_by_builtin_key: dict[str, HandleDirection] = {
        "blueprint.input": "target",
        "blueprint.output": "source",
    }
    for node in nodes:
        direction = direction_by_builtin_key.get(node.builtin_key or "")
        if direction is None:
            continue
        options = options_by_direction.get(direction, [])
        option_metadata = {
            option.id: option.model_dump(mode="json") for option in options
        }
        for input_item in node.inputs:
            if input_item.name != "public_handle_config_id":
                continue
            input_item.options = [
                ActionNodeOption(
                    label=f"{option.label}（{option.handle_name}）",
                    value=option.id,
                )
                for option in options
            ]
            input_item.custom_props = {
                **(input_item.custom_props or {}),
                "option_metadata": option_metadata,
            }
