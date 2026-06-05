from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

from .capture import PlaywrightCaptureConfig, PlaywrightSnapshotCapturer
from .cos_storage import CosStorage
from .service import SnapshotService

def build_service(
    *,
    headed: bool = False,
    extra_http_headers: dict[str, str] | None = None,
    proxy: str | None = None,
    max_concurrency: int | None = None,
    max_retries: int | None = None,
) -> SnapshotService:
    proxy_server = proxy if proxy is not None else os.getenv("DOWNLOAD_PROXY")
    concurrency = 4 if max_concurrency is None else max_concurrency
    retries = 3 if max_retries is None else max_retries
    capturer = PlaywrightSnapshotCapturer(
        PlaywrightCaptureConfig(
            headless=not headed,
            page_timeout_ms=60_000,
            wait_after_load_ms=1_500,
            viewport_width=1440,
            viewport_height=900,
            proxy_server=proxy_server,
            extra_http_headers=extra_http_headers,
            max_concurrency=concurrency,
            max_retries=retries,
        )
    )
    return SnapshotService(storage=CosStorage.from_env(), capturer=capturer)
