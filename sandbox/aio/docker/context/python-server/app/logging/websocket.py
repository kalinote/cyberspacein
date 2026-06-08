from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

from app.logging.sanitizer import sanitize_for_logging


def log_websocket_event(
    logger: logging.Logger,
    event: str,
    *,
    websocket: WebSocket,
    route: str,
    session_id: str | None = None,
    level: int = logging.INFO,
    details: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "route": route,
        "path": websocket.url.path,
        "client_ip": websocket.client.host if websocket.client else "-",
    }

    if session_id is not None:
        payload["session_id"] = session_id

    if websocket.query_params:
        payload["query"] = sanitize_for_logging(
            dict(websocket.query_params),
            field_name="query",
        )

    if details:
        payload["details"] = sanitize_for_logging(
            details,
            field_name="details",
            include_bulky_preview=level >= logging.ERROR,
        )

    logger.log(
        level,
        "WEBSOCKET_EVENT %s",
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
