from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import uuid4

from loguru import logger

from .capture import PlaywrightSnapshotCapturer
from .cos_storage import CosStorage
from .models import PageSnapshotRecord, SnapshotRunResult


@dataclass(slots=True)
class SnapshotService:
    storage: CosStorage
    capturer: PlaywrightSnapshotCapturer

    def run(self, url: str) -> SnapshotRunResult:
        seed_url = url.strip()
        if not seed_url:
            raise ValueError("链接不能为空")
        return self.run_many([seed_url])

    def run_many(self, urls: list[str]) -> SnapshotRunResult:
        normalized = [u.strip() for u in urls if u.strip()]
        if not normalized:
            raise ValueError("链接列表不能为空")
        task_id = uuid4().hex
        seed_url = normalized[0]
        t0 = time.perf_counter()
        captured_list = self.capturer.capture_many(normalized)
        t_capture = time.perf_counter()
        if not captured_list:
            raise RuntimeError("所有页面采集均失败")
        pages = []
        storage = self.storage
        for captured in captured_list:
            payload = captured.payload
            screenshot_key = storage.object_key(payload.screenshot_bytes, ".png")
            storage.upload_bytes(
                screenshot_key, payload.screenshot_bytes, "image/png"
            )
            mhtml_key = ""
            if payload.mhtml_bytes:
                mhtml_key = storage.object_key(payload.mhtml_bytes, ".mhtml")
                storage.upload_bytes(
                    mhtml_key,
                    payload.mhtml_bytes,
                    "application/x-mimearchive",
                )
            pages.append(
                PageSnapshotRecord(
                    url=captured.url,
                    screenshot_key=screenshot_key,
                    mhtml_key=mhtml_key,
                )
            )
        t1 = time.perf_counter()
        max_page_duration = max(c.page_duration_seconds for c in captured_list)
        result = SnapshotRunResult(
            task_id=task_id,
            seed_url=seed_url,
            bucket=self.storage.bucket,
            pages=pages,
            capture_elapsed_seconds=captured_list[0].capture_elapsed_seconds,
            total_elapsed_seconds=t1 - t0,
            page_duration_seconds=max_page_duration,
        )
        logger.info(f"对象存储上传用时: {t1 - t_capture:.2f} 秒")
        return result
