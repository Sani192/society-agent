from __future__ import annotations

from dataclasses import dataclass

from app.channels.whatsapp.session_repository import InMemorySessionRepository


@dataclass
class JoinSessionState:
    pending_action: str | None = None
    join_code: str | None = None


_REPOSITORY: InMemorySessionRepository[JoinSessionState] = InMemorySessionRepository()


def build_join_session_key(*, sender_id: str | None) -> str | None:
    return sender_id


def get_join_session(session_key: str | None) -> JoinSessionState | None:
    return _REPOSITORY.get(session_key)


def save_join_session(session_key: str | None, state: JoinSessionState) -> None:
    _REPOSITORY.save(session_key, state)


def clear_join_session(session_key: str | None) -> None:
    _REPOSITORY.clear(session_key)
