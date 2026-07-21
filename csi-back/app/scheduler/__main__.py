import asyncio
import signal
import sys
from contextlib import suppress

from loguru import logger

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.mongodb import close_mongodb, init_mongodb
from app.db.redis import close_redis, init_redis
from app.service.action_schedule import ActionScheduleService, utc_now

logger = logger.bind(name=__name__)


async def run_scheduler() -> None:
    """运行独立的行动调度扫描循环。"""
    await init_mongodb()
    await init_redis()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)
    logger.info("行动调度器已启动")
    try:
        while not stop_event.is_set():
            scan_at = utc_now()
            try:
                recovered = await ActionScheduleService.recover_ready_actions()
                triggered = await ActionScheduleService.scan_due_schedules(scan_at)
                await ActionScheduleService.heartbeat(scan_at)
                if recovered or triggered:
                    logger.info(f"调度扫描完成，恢复 {recovered} 个行动，处理 {triggered} 个计划")
            except Exception as exc:
                logger.exception(f"行动调度扫描失败: {exc}")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.ACTION_SCHEDULER_POLL_SECONDS,
                )
            except TimeoutError:
                pass
    finally:
        await close_redis()
        await close_mongodb()
        logger.info("行动调度器已停止")


async def healthcheck() -> int:
    """通过 Redis 心跳检查行动调度器是否在线。"""
    try:
        await init_redis()
        online, _, _ = await ActionScheduleService.scheduler_status()
        return 0 if online else 1
    except Exception:
        return 1
    finally:
        await close_redis()


def main() -> None:
    """解析命令并启动调度器或执行健康检查。"""
    setup_logging()
    if len(sys.argv) > 1 and sys.argv[1] == "healthcheck":
        raise SystemExit(asyncio.run(healthcheck()))
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
