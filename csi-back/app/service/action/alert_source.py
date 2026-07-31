"""行动实例告警源服务。"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from app.models.action.action import ActionInstanceModel
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.observation import AlertObservation, AlertObservationPage
from app.schemas.alert.source import (
    AlertEnumOption,
    AlertFieldDescriptor,
    AlertSourceDescriptor,
)
from app.schemas.constants import ActionFlowStatusEnum
from app.service.alert.observation_inbox import AlertObservationInboxService
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)


def as_utc(value: datetime) -> datetime:
    """将业务时间转换为带时区 UTC。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def action_status_observation(
    action: ActionInstanceModel,
    status: ActionFlowStatusEnum,
    observed_at: datetime,
) -> AlertObservation:
    """把行动状态快照转换为统一告警观测。"""
    observed_at = as_utc(observed_at)
    version_key = observed_at.isoformat()
    return AlertObservation(
        observation_id=generate_id(
            f"action.instance:{action.id}:status:{status.value}:{version_key}"
        ),
        source_key="action.instance",
        resource_type="action_instance",
        resource_id=action.id,
        resource_name=action.blueprint_snapshot.name,
        resource_url=f"/action/{action.id}",
        field_key="status",
        signal_key="execution_status",
        value_type=AlertValueTypeEnum.ENUM,
        value=status.value,
        observed_at=observed_at,
        source_event_id=(
            f"action:{action.id}:status:{status.value}:{version_key}"
        ),
        metadata={},
    )


async def publish_action_status_observation(
    action: ActionInstanceModel,
    status: ActionFlowStatusEnum,
    observed_at: datetime,
) -> bool:
    """可靠发布行动状态变化，失败时交由周期补偿扫描。"""
    try:
        return await AlertObservationInboxService.publish(
            action_status_observation(action, status, observed_at)
        )
    except Exception as exc:
        logger.warning(
            f"行动状态告警观测发布失败，Action ID: {getattr(action, 'id', 'unknown')}, 状态: {status.value}: {exc}"
        )
        return False


class ActionInstanceAlertSource:
    """行动系统向告警中心提供的实例状态数据源。"""

    def describe(self) -> AlertSourceDescriptor:
        """声明行动实例状态字段及其检测能力。"""
        modes = [
            AlertEvaluationModeEnum.REALTIME,
            AlertEvaluationModeEnum.INTERVAL,
            AlertEvaluationModeEnum.HYBRID,
        ]
        return AlertSourceDescriptor(
            source_key="action.instance",
            module_key="action",
            module_name="行动系统",
            resource_type="action_instance",
            resource_name="行动",
            schema_version=1,
            fields=[
                AlertFieldDescriptor(
                    field_key="status",
                    field_name="状态",
                    signal_key="execution_status",
                    value_type=AlertValueTypeEnum.ENUM,
                    enum_options=[
                        AlertEnumOption(
                            value=status.value,
                            label={
                                ActionFlowStatusEnum.UNKNOWN: "未知",
                                ActionFlowStatusEnum.UNREADY: "未就绪",
                                ActionFlowStatusEnum.READY: "就绪",
                                ActionFlowStatusEnum.RUNNING: "运行中",
                                ActionFlowStatusEnum.COMPLETED: "已完成",
                                ActionFlowStatusEnum.FAILED: "失败",
                                ActionFlowStatusEnum.CANCELLED: "已取消",
                                ActionFlowStatusEnum.TIMEOUT: "超时",
                                ActionFlowStatusEnum.PAUSED: "已暂停",
                                ActionFlowStatusEnum.STOPPED: "已停止",
                            }[status],
                        )
                        for status in ActionFlowStatusEnum
                    ],
                    supported_operators=[
                        AlertOperatorEnum.EQ,
                        AlertOperatorEnum.NE,
                        AlertOperatorEnum.IN,
                        AlertOperatorEnum.NOT_IN,
                    ],
                    supported_evaluation_modes=modes,
                    default_interval_seconds=300,
                    initial_evaluation_policy=(
                        AlertInitialEvaluationPolicyEnum.FROM_ACTIVATION
                    ),
                )
            ],
            supported_evaluation_modes=modes,
        )

    async def iter_observations(
        self,
        *,
        field_key: str,
        active_from: datetime,
        cursor: str | None,
        limit: int,
    ) -> AlertObservationPage:
        """分页读取规则生效后发生过状态变化的行动。"""
        if field_key != "status":
            raise ValueError(f"行动告警源不支持字段: {field_key}")
        query: dict = {
            "is_deleted": False,
            "updated_at": {"$gte": active_from},
        }
        if cursor:
            query["_id"] = {"$gt": cursor}
        actions = await ActionInstanceModel.find(query).sort("+_id").limit(limit).to_list()
        items = [
            action_status_observation(
                action,
                action.status,
                action.updated_at or action.created_at,
            )
            for action in actions
        ]
        return AlertObservationPage(
            items=items,
            next_cursor=actions[-1].id if len(actions) == limit else None,
        )
