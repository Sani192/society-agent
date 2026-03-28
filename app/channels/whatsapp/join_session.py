from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JoinSessionState:
    pending_action: str | None = None
    join_code: str | None = None


_JOIN_SESSIONS: dict[str, JoinSessionState] = {}


def build_join_session_key(*, sender_id: str | None) -> str | None:
    return sender_id


def get_join_session(session_key: str | None) -> JoinSessionState | None:
    if not session_key:
        return None
    return _JOIN_SESSIONS.get(session_key)


def save_join_session(session_key: str | None, state: JoinSessionState) -> None:
    if not session_key:
        return
    _JOIN_SESSIONS[session_key] = state


def clear_join_session(session_key: str | None) -> None:
    if not session_key:
        return
    _JOIN_SESSIONS.pop(session_key, None)

