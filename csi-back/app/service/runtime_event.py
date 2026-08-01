from __future__ import annotations

from loguru import logger
from pymongo.errors import DuplicateKeyError

from app.models.action.action import ActionInstanceModel
from app.models.runtime_event import RuntimeDomainEventModel
from app.schemas.constants import ActionVisibilityEnum


class RuntimeDomainEventService:
    """发布运行时之间的幂等持久化领域事件。"""

    ACTION_TERMINAL = "action.terminal"

    @staticmethod
    async def publish_action_terminal(
        action: ActionInstanceModel,
        status: str,
    ) -> bool:
        """为嵌入式子行动发布一次确定性的终态事件。"""
        if (
            getattr(action, "visibility", ActionVisibilityEnum.NORMAL)
            != ActionVisibilityEnum.EMBEDDED
            or not getattr(action, "parent_node_execution_id", None)
        ):
            return False
        try:
            event = RuntimeDomainEventModel(
                id=f"{RuntimeDomainEventService.ACTION_TERMINAL}:{action.id}",
                topic=RuntimeDomainEventService.ACTION_TERMINAL,
                aggregate_type="action",
                aggregate_id=action.id,
                payload={
                    "action_id": action.id,
                    "status": status,
                    "parent_action_id": getattr(
                        action,
                        "parent_action_id",
                        None,
                    ),
                    "parent_node_instance_id": getattr(
                        action,
                        "parent_node_instance_id",
                        None,
                    ),
                    "parent_node_execution_id": (
                        action.parent_node_execution_id
                    ),
                },
            )
            await event.insert()
        except DuplicateKeyError:
            return True
        except Exception as exc:
            logger.warning(
                f"子行动终态事件发布失败，Action ID: {action.id}: {exc}"
            )
            return False
        return True
