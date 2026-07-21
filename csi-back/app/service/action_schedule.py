import json
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from loguru import logger

from app.core.config import settings
from app.db.redis import get_redis
from app.models.action.action import ActionInstanceModel
from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.action.schedule import ActionSchedulePayload
from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionScheduleMisfirePolicyEnum,
    ActionScheduleOverlapPolicyEnum,
    ActionScheduleTypeEnum,
    ActionTriggerTypeEnum,
)
from app.service.action import ActionInstanceService

logger = logger.bind(name=__name__)

SCHEDULER_HEARTBEAT_KEY = "action:scheduler:heartbeat"
ACTIVE_ACTION_STATUSES = {
    ActionFlowStatusEnum.UNKNOWN,
    ActionFlowStatusEnum.UNREADY,
    ActionFlowStatusEnum.READY,
    ActionFlowStatusEnum.RUNNING,
    ActionFlowStatusEnum.PAUSED,
}


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """将数据库或请求时间统一转换为带时区 UTC 时间。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_timezone(name: str) -> ZoneInfo:
    """校验并返回 IANA 时区。"""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"无效时区: {name}") from exc


def validate_cron_expression(expression: str) -> str:
    """校验标准五段 Cron 表达式。"""
    normalized = " ".join(expression.strip().split())
    if len(normalized.split(" ")) != 5 or not croniter.is_valid(normalized):
        raise ValueError("仅支持标准五段 Cron 表达式")
    return normalized


def calculate_next_runs(
    schedule_type: ActionScheduleTypeEnum,
    *,
    cron_expression: str | None,
    interval_seconds: int | None,
    timezone_name: str,
    start_at: datetime,
    end_at: datetime | None,
    now: datetime | None = None,
    count: int = 5,
) -> list[datetime]:
    """从当前时刻开始计算未来执行时间，返回 UTC。"""
    current = as_utc(now or utc_now())
    start = as_utc(start_at)
    end = as_utc(end_at) if end_at else None
    results: list[datetime] = []
    if schedule_type == ActionScheduleTypeEnum.CRON:
        expression = validate_cron_expression(cron_expression or "")
        local_zone = validate_timezone(timezone_name)
        base = max(current, start).astimezone(local_zone)
        iterator = croniter(expression, base)
        if start > current and croniter.match(expression, base):
            candidate_utc = as_utc(base)
            if not end or candidate_utc <= end:
                results.append(candidate_utc)
        for _ in range(count):
            if len(results) >= count:
                break
            candidate = iterator.get_next(datetime)
            candidate_utc = as_utc(candidate)
            if end and candidate_utc > end:
                break
            results.append(candidate_utc)
        return results

    if interval_seconds is None or interval_seconds < 60:
        raise ValueError("固定间隔不得小于 60 秒")
    candidate = start
    if candidate <= current:
        elapsed = (current - candidate).total_seconds()
        candidate += timedelta(seconds=(int(elapsed // interval_seconds) + 1) * interval_seconds)
    for _ in range(count):
        if end and candidate > end:
            break
        results.append(candidate)
        candidate += timedelta(seconds=interval_seconds)
    return results


def latest_due_time(schedule: ActionScheduleModel, now: datetime) -> datetime:
    """计算错过多个周期时最近一个应执行时刻。"""
    current = as_utc(now)
    start = as_utc(schedule.start_at)
    if schedule.schedule_type == ActionScheduleTypeEnum.INTERVAL:
        interval = schedule.interval_seconds or 60
        if current <= start:
            return start
        elapsed = int((current - start).total_seconds())
        return start + timedelta(seconds=(elapsed // interval) * interval)
    local_zone = validate_timezone(schedule.timezone)
    iterator = croniter(validate_cron_expression(schedule.cron_expression or ""), current.astimezone(local_zone))
    candidate = as_utc(iterator.get_prev(datetime))
    return max(candidate, start)


def validate_blueprint_params(blueprint: ActionBlueprintModel, params: dict) -> None:
    """校验计划保存的蓝图模板参数。"""
    if not blueprint.is_template:
        if params:
            raise ValueError("非模板蓝图不能保存模板参数")
        return
    template_params = (blueprint.template or {}).get("params") or []
    definitions = {item.get("name"): item for item in template_params if item.get("name")}
    unknown = set(params) - set(definitions)
    if unknown:
        raise ValueError(f"包含未知模板参数: {', '.join(sorted(unknown))}")
    for name, definition in definitions.items():
        value = params.get(name)
        if definition.get("required") and (value is None or value == "" or value == []):
            raise ValueError(f"缺少必填模板参数: {name}")
        if value is None:
            continue
        param_type = definition.get("type")
        if param_type == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"模板参数 {name} 必须为整数")
        if param_type in {"boolean", "checkbox"} and not isinstance(value, bool):
            raise ValueError(f"模板参数 {name} 必须为布尔值")
        if param_type in {"tags", "conditions", "checkbox-group"} and not isinstance(value, list):
            raise ValueError(f"模板参数 {name} 必须为数组")


class ActionScheduleService:
    """行动周期计划的校验、触发与恢复服务。"""

    @staticmethod
    async def validate_payload(payload: ActionSchedulePayload) -> ActionBlueprintModel:
        """校验计划、蓝图和模板参数。"""
        validate_timezone(payload.timezone)
        if payload.schedule_type == ActionScheduleTypeEnum.CRON:
            payload.cron_expression = validate_cron_expression(payload.cron_expression or "")
        elif payload.interval_seconds is None or payload.interval_seconds < 60:
            raise ValueError("固定间隔不得小于 60 秒")
        blueprint = await ActionBlueprintModel.find_one({"_id": payload.blueprint_id, "is_deleted": False})
        if blueprint is None:
            raise ValueError("行动蓝图不存在或已删除")
        validate_blueprint_params(blueprint, payload.params)
        calculate_next_runs(
            payload.schedule_type,
            cron_expression=payload.cron_expression,
            interval_seconds=payload.interval_seconds,
            timezone_name=payload.timezone,
            start_at=payload.start_at,
            end_at=payload.end_at,
            count=1,
        )
        return blueprint

    @staticmethod
    def next_runs(payload: ActionSchedulePayload, count: int = 5) -> list[datetime]:
        """计算计划未来执行时刻。"""
        return calculate_next_runs(
            payload.schedule_type,
            cron_expression=payload.cron_expression,
            interval_seconds=payload.interval_seconds,
            timezone_name=payload.timezone,
            start_at=payload.start_at,
            end_at=payload.end_at,
            count=count,
        )

    @staticmethod
    async def _acquire_lock(schedule_id: str) -> str | None:
        """获取计划级 Redis 短锁。"""
        redis = get_redis()
        if redis is None:
            raise RuntimeError("Redis 未初始化")
        token = secrets.token_urlsafe(18)
        acquired = await redis.set(
            f"action:schedule-lock:{schedule_id}",
            token,
            ex=settings.ACTION_SCHEDULER_LOCK_SECONDS,
            nx=True,
        )
        return token if acquired else None

    @staticmethod
    async def _release_lock(schedule_id: str, token: str) -> None:
        """仅释放当前持有者的计划锁。"""
        redis = get_redis()
        if redis is None:
            return
        await redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            1,
            f"action:schedule-lock:{schedule_id}",
            token,
        )

    @staticmethod
    async def trigger_due_schedule(schedule_id: str, now: datetime | None = None) -> str | None:
        """幂等触发一个已到期计划并返回 Action ID。"""
        token = await ActionScheduleService._acquire_lock(schedule_id)
        if token is None:
            return None
        try:
            schedule = await ActionScheduleModel.find_one({"_id": schedule_id, "is_deleted": False})
            current = as_utc(now or utc_now())
            if schedule is None or not schedule.enabled or schedule.next_run_at is None:
                return None
            due = as_utc(schedule.next_run_at)
            if due > current:
                return None
            if schedule.end_at and current > as_utc(schedule.end_at):
                schedule.enabled = False
                schedule.next_run_at = None
                schedule.last_trigger_status = "expired"
                schedule.updated_at = current
                await schedule.save()
                return None

            grace_seconds = max(settings.ACTION_SCHEDULER_POLL_SECONDS * 2, 30)
            missed = (current - due).total_seconds() > grace_seconds
            next_runs = calculate_next_runs(
                schedule.schedule_type,
                cron_expression=schedule.cron_expression,
                interval_seconds=schedule.interval_seconds,
                timezone_name=schedule.timezone,
                start_at=schedule.start_at,
                end_at=schedule.end_at,
                now=current,
                count=1,
            )
            next_run_at = next_runs[0] if next_runs else None
            if missed and schedule.misfire_policy == ActionScheduleMisfirePolicyEnum.SKIP:
                schedule.next_run_at = next_run_at
                schedule.last_scheduled_for = due
                schedule.last_trigger_status = "skipped_misfire"
                schedule.last_error = None
                schedule.enabled = next_run_at is not None
                schedule.updated_at = current
                await schedule.save()
                return None
            scheduled_for = latest_due_time(schedule, current) if missed else due

            if schedule.overlap_policy == ActionScheduleOverlapPolicyEnum.FORBID:
                active = await ActionInstanceModel.find_one(
                    {"schedule_id": schedule.id, "status": {"$in": list(ACTIVE_ACTION_STATUSES)}}
                )
                if active is not None:
                    schedule.next_run_at = next_run_at
                    schedule.last_scheduled_for = scheduled_for
                    schedule.last_trigger_status = "skipped_overlap"
                    schedule.last_error = None
                    schedule.enabled = next_run_at is not None
                    schedule.updated_at = current
                    await schedule.save()
                    return None

            blueprint = await ActionBlueprintModel.find_one({"_id": schedule.blueprint_id, "is_deleted": False})
            if blueprint is None:
                schedule.enabled = False
                schedule.next_run_at = None
                schedule.last_trigger_status = "invalid"
                schedule.last_error = "行动蓝图不存在或已删除"
                schedule.updated_at = current
                await schedule.save()
                return None
            try:
                validate_blueprint_params(blueprint, schedule.params)
            except ValueError as exc:
                schedule.enabled = False
                schedule.next_run_at = None
                schedule.last_trigger_status = "invalid"
                schedule.last_error = str(exc)
                schedule.updated_at = current
                await schedule.save()
                return None

            trigger_key = f"schedule:{schedule.id}:{scheduled_for.isoformat()}"
            ok, action_id = await ActionInstanceService.init(
                schedule.blueprint_id,
                schedule.params or None,
                trigger_type=ActionTriggerTypeEnum.SCHEDULED,
                trigger_key=trigger_key,
                scheduled_for=scheduled_for,
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                schedule_priority=schedule.priority,
            )
            if not ok:
                schedule.last_trigger_status = "failed"
                schedule.last_error = action_id
                schedule.updated_at = current
                await schedule.save()
                return None
            schedule.next_run_at = next_run_at
            schedule.last_scheduled_for = scheduled_for
            schedule.last_action_id = action_id
            schedule.last_trigger_status = "created"
            schedule.last_error = None
            schedule.enabled = next_run_at is not None
            schedule.updated_at = current
            await schedule.save()
        except Exception as exc:
            logger.exception(f"触发行动计划失败，计划 ID: {schedule_id}，错误: {exc}")
            schedule = await ActionScheduleModel.find_one({"_id": schedule_id})
            if schedule is not None:
                schedule.last_trigger_status = "failed"
                schedule.last_error = str(exc)
                schedule.updated_at = utc_now()
                await schedule.save()
            return None
        finally:
            await ActionScheduleService._release_lock(schedule_id, token)

        await ActionInstanceService.start(action_id)
        return action_id

    @staticmethod
    async def scan_due_schedules(now: datetime | None = None) -> int:
        """扫描并触发一批到期计划。"""
        current = as_utc(now or utc_now())
        schedules = await ActionScheduleModel.find(
            {
                "enabled": True,
                "is_deleted": False,
                "next_run_at": {"$lte": current},
            }
        ).sort([("next_run_at", 1), ("priority", -1)]).limit(settings.ACTION_SCHEDULER_BATCH_SIZE).to_list()
        for schedule in schedules:
            await ActionScheduleService.trigger_due_schedule(schedule.id, current)
        return len(schedules)

    @staticmethod
    async def recover_ready_actions() -> int:
        """恢复已经创建但尚未启动的定时 Action。"""
        actions = await ActionInstanceModel.find(
            {"schedule_id": {"$type": "string"}, "status": ActionFlowStatusEnum.READY}
        ).limit(settings.ACTION_SCHEDULER_BATCH_SIZE).to_list()
        for action in actions:
            await ActionInstanceService.start(action.id)
        return len(actions)

    @staticmethod
    async def heartbeat(last_scan_at: datetime) -> None:
        """写入 Scheduler 进程心跳。"""
        redis = get_redis()
        if redis is None:
            return
        now = utc_now()
        await redis.set(
            SCHEDULER_HEARTBEAT_KEY,
            json.dumps({"heartbeat_at": now.isoformat(), "last_scan_at": as_utc(last_scan_at).isoformat()}),
            ex=settings.ACTION_SCHEDULER_HEARTBEAT_TTL_SECONDS,
        )

    @staticmethod
    async def scheduler_status() -> tuple[bool, datetime | None, datetime | None]:
        """读取 Scheduler 在线状态和最近扫描时间。"""
        redis = get_redis()
        if redis is None:
            return False, None, None
        raw = await redis.get(SCHEDULER_HEARTBEAT_KEY)
        if not raw:
            return False, None, None
        data = json.loads(raw)
        heartbeat = datetime.fromisoformat(data["heartbeat_at"])
        last_scan = datetime.fromisoformat(data["last_scan_at"])
        online = (utc_now() - as_utc(heartbeat)).total_seconds() <= settings.ACTION_SCHEDULER_HEARTBEAT_TTL_SECONDS
        return online, heartbeat, last_scan
