import asyncio
import os
import signal
import socket
import sys
from contextlib import suppress
from uuid import uuid4

from loguru import logger

from app.core.logging_config import setup_logging
from app.db.mongodb import close_mongodb, init_mongodb
from app.db.redis import close_redis, init_redis
from app.service.alert_source_bootstrap import register_builtin_alert_sources
from app.service.alert.worker import AlertWorkerService

logger = logger.bind(name=__name__)


async def run_worker() -> None:
    """初始化依赖并运行独立告警处理循环。"""
    await init_mongodb()
    await init_redis()
    register_builtin_alert_sources()
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    worker = AlertWorkerService(worker_id)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)
    tasks = [
        asyncio.create_task(worker.observation_loop(stop_event)),
        asyncio.create_task(worker.rule_loop(stop_event)),
        asyncio.create_task(worker.outbox_loop(stop_event)),
        asyncio.create_task(worker.heartbeat_loop(stop_event)),
    ]
    logger.info(f"告警 Worker 已启动: {worker_id}")
    try:
        await stop_event.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await worker.clear_heartbeat()
        await close_redis()
        await close_mongodb()
        logger.info(f"告警 Worker 已停止: {worker_id}")


async def healthcheck() -> int:
    """通过 Redis 心跳检查告警 Worker 是否在线。"""
    try:
        await init_redis()
        status = await AlertWorkerService.status()
        return 0 if status.get("online") else 1
    except Exception:
        return 1
    finally:
        await close_redis()


def main() -> None:
    """解析命令并启动 Worker 或执行健康检查。"""
    setup_logging()
    if len(sys.argv) > 1 and sys.argv[1] == "healthcheck":
        raise SystemExit(asyncio.run(healthcheck()))
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
