from __future__ import annotations

from .cos_storage import CosStorage
from .models import PageSnapshotRecord, SnapshotRunResult


def upload_snapshot(
    storage: CosStorage,
    seed_url: str,
    task_id: str,
    url: str,
    screenshot: bytes,
    mhtml: bytes,
) -> SnapshotRunResult:
    screenshot_key, mhtml_key = storage.upload_snapshot(screenshot, mhtml)
    return SnapshotRunResult(
        task_id=task_id,
        seed_url=seed_url,
        bucket=storage.bucket,
        pages=[
            PageSnapshotRecord(
                url=url,
                screenshot_key=screenshot_key,
                mhtml_key=mhtml_key,
            )
        ],
    )
