from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PageSnapshotRecord:
    url: str
    screenshot_key: str
    mhtml_key: str


@dataclass(slots=True)
class SnapshotRunResult:
    task_id: str
    seed_url: str
    bucket: str
    pages: list[PageSnapshotRecord] = field(default_factory=list)
    capture_elapsed_seconds: float = 0.0
    total_elapsed_seconds: float = 0.0
    page_duration_seconds: float = 0.0
