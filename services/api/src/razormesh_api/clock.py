"""Timezone-aware UTC clock abstraction (testable; no naive datetimes for expiry)."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)
