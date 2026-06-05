"""网页快照 SDK。"""

from . import _env  # noqa: F401

from .capture import PlaywrightCaptureConfig, PlaywrightSnapshotCapturer
from .factory import build_service
from .models import PageSnapshotRecord, SnapshotRunResult
from .service import SnapshotService

__all__ = [
    "PlaywrightCaptureConfig",
    "PlaywrightSnapshotCapturer",
    "PageSnapshotRecord",
    "SnapshotRunResult",
    "SnapshotService",
    "build_service",
]
