from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommitteeActionSessionState:
    action: str
    step: str
    data: dict[str, str] = field(default_factory=dict)


_COMMITTEE_ACTION_SESSIONS: dict[str, CommitteeActionSessionState] = {}


def build_committee_action_session_key(*, member_id: str | None, sender_id: str | None) -> str | None:
    if member_id and sender_id:
        return f"{member_id}:{sender_id}"
    return member_id or sender_id


def get_committee_action_session(session_key: str | None) -> CommitteeActionSessionState | None:
    if not session_key:
        return None
    return _COMMITTEE_ACTION_SESSIONS.get(session_key)


def save_committee_action_session(
    session_key: str | None,
    state: CommitteeActionSessionState,
) -> None:
    if not session_key:
        return
    _COMMITTEE_ACTION_SESSIONS[session_key] = state


def clear_committee_action_session(session_key: str | None) -> None:
    if not session_key:
        return
    _COMMITTEE_ACTION_SESSIONS.pop(session_key, None)
