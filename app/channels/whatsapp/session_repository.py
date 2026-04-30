from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
SCHEMA_VERSION = 1


@dataclass
class StoredSessionState(Generic[T]):
    schema_version: int
    payload: T


class InMemorySessionRepository(Generic[T]):
    def __init__(self) -> None:
        self._store: dict[str, StoredSessionState[T]] = {}

    def get(self, session_key: str | None) -> T | None:
        if not session_key:
            return None
        session = self._store.get(session_key)
        if not session or session.schema_version != SCHEMA_VERSION:
            return None
        return session.payload

    def save(self, session_key: str | None, state: T) -> None:
        if not session_key:
            return
        self._store[session_key] = StoredSessionState(schema_version=SCHEMA_VERSION, payload=state)

    def clear(self, session_key: str | None) -> None:
        if not session_key:
            return
        self._store.pop(session_key, None)
