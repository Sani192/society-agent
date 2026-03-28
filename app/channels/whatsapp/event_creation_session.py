from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class EventCreationSessionState:
    step: str = "name"
    name: str | None = None
    event_date: datetime | None = None
    food_types: list[str] | None = None
    charge_per_adult: int | None = None
    charge_per_child: int | None = None


_EVENT_CREATION_SESSIONS: dict[str, EventCreationSessionState] = {}


def build_event_creation_session_key(
    *,
    member_id: str | None,
    sender_id: str | None,
) -> str | None:
    if member_id and sender_id:
        return f"{member_id}:{sender_id}"
    return member_id or sender_id


def get_event_creation_session(
    session_key: str | None,
) -> EventCreationSessionState | None:
    if not session_key:
        return None
    return _EVENT_CREATION_SESSIONS.get(session_key)


def save_event_creation_session(
    session_key: str | None,
    state: EventCreationSessionState,
) -> None:
    if not session_key:
        return
    _EVENT_CREATION_SESSIONS[session_key] = state


def clear_event_creation_session(session_key: str | None) -> None:
    if not session_key:
        return
    _EVENT_CREATION_SESSIONS.pop(session_key, None)
