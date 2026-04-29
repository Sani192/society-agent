from __future__ import annotations

import heapq
from datetime import datetime, timezone
from typing import Protocol

from app.utils.operational_metrics import increment_counter

MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_SECONDS = 2
MAX_RETRY_BACKOFF_SECONDS = 60


class RetryQueueBackend(Protocol):
    def push(self, run_after: float, envelope_id: str, payload_dict: dict, attempt: int) -> None: ...

    def pop_due(self, now_ts: float) -> list[tuple[str, dict, int]]: ...


class InMemoryRetryQueue:
    def __init__(self) -> None:
        self._q: list[tuple[float, str, dict, int]] = []

    def push(self, run_after: float, envelope_id: str, payload_dict: dict, attempt: int) -> None:
        heapq.heappush(self._q, (run_after, envelope_id, payload_dict, attempt))

    def pop_due(self, now_ts: float) -> list[tuple[str, dict, int]]:
        ready: list[tuple[str, dict, int]] = []
        while self._q and self._q[0][0] <= now_ts:
            _, envelope_id, payload, attempt = heapq.heappop(self._q)
            ready.append((envelope_id, payload, attempt))
        return ready


def schedule_retry(queue: RetryQueueBackend, *, envelope_id: str, payload_dict: dict, attempt: int) -> None:
    backoff = min(RETRY_BASE_SECONDS * (2 ** max(attempt - 1, 0)), MAX_RETRY_BACKOFF_SECONDS)
    queue.push(datetime.now(timezone.utc).timestamp() + float(backoff), envelope_id, payload_dict, attempt)
    increment_counter("whatsapp.webhook.retries_scheduled")

RETRY_QUEUE = InMemoryRetryQueue()

