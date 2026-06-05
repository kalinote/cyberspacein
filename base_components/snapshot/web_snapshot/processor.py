from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from loguru import logger

from .capture import CapturePayload, CaptureResult

if TYPE_CHECKING:
    from .service import SnapshotService


@dataclass(slots=True)
class QueueMessageItem:
    data: dict
    delivery_tag: int


def _extract_url(data: dict, url_field: str) -> str | None:
    raw_url = data.get(url_field)
    if not raw_url or not isinstance(raw_url, str):
        return None
    url = raw_url.strip()
    return url or None


def upload_capture_payload(
    service: SnapshotService,
    url: str,
    payload: CapturePayload,
) -> tuple[str | None, str | None]:
    storage = service.storage
    screenshot_url: str | None = None
    snapshot_url: str | None = None

    try:
        screenshot_key = storage.object_key(payload.screenshot_bytes, ".png")
        storage.upload_bytes(screenshot_key, payload.screenshot_bytes, "image/png")
        screenshot_url = storage.public_url(screenshot_key)
    except Exception as exc:
        logger.error(f"截图上传失败: {url} - {exc}")

    if payload.mhtml_bytes:
        try:
            mhtml_key = storage.object_key(payload.mhtml_bytes, ".mhtml")
            storage.upload_bytes(
                mhtml_key, payload.mhtml_bytes, "application/x-mimearchive"
            )
            snapshot_url = storage.public_url(mhtml_key)
        except Exception as exc:
            logger.error(f"MHTML 上传失败: {url} - {exc}")

    return screenshot_url, snapshot_url


def enrich_data_with_urls(
    data: dict,
    screenshot_url: str | None,
    snapshot_url: str | None,
) -> dict:
    out = data.copy()
    if screenshot_url:
        out["screenshot"] = screenshot_url
    if snapshot_url:
        out["snapshot"] = snapshot_url
    return out


def process_message_batch(
    items: list[QueueMessageItem],
    service: SnapshotService,
    url_field: str = "url",
    *,
    heartbeat_callback: Callable[[], None] | None = None,
) -> list[dict]:
    if heartbeat_callback:
        heartbeat_callback()

    url_order: list[str] = []
    url_seen: set[str] = set()
    for item in items:
        url = _extract_url(item.data, url_field)
        if url and url not in url_seen:
            url_seen.add(url)
            url_order.append(url)

    captured_by_url: dict[str, CaptureResult] = {}
    if url_order:
        for captured in service.capturer.capture_many(url_order):
            captured_by_url[captured.url] = captured
        if heartbeat_callback:
            heartbeat_callback()

    results: list[dict] = []
    for item in items:
        url = _extract_url(item.data, url_field)
        if not url:
            logger.warning(f"数据中未找到有效字段 '{url_field}'，原样输出")
            results.append(item.data.copy())
            continue

        captured = captured_by_url.get(url)
        if not captured:
            logger.error(f"页面抓取失败，原样输出: {url}")
            results.append(item.data.copy())
            continue

        screenshot_url, snapshot_url = upload_capture_payload(
            service, url, captured.payload
        )
        results.append(
            enrich_data_with_urls(item.data, screenshot_url, snapshot_url)
        )

    return results
