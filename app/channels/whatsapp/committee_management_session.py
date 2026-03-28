from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommitteeManagementSessionState:
    pending_action: str | None = None
    selected_member_id: str | None = None
    selected_role: str | None = None


_COMMITTEE_MANAGEMENT_SESSIONS: dict[str, CommitteeManagementSessionState] = {}


def build_committee_management_session_key(*, sender_id: str | None) -> str | None:
    return sender_id


def get_committee_management_session(session_key: str | None) -> CommitteeManagementSessionState | None:
    if not session_key:
        return None
    return _COMMITTEE_MANAGEMENT_SESSIONS.get(session_key)


def save_committee_management_session(session_key: str | None, state: CommitteeManagementSessionState) -> None:
    if not session_key:
        return
    _COMMITTEE_MANAGEMENT_SESSIONS[session_key] = state


def clear_committee_management_session(session_key: str | None) -> None:
    if not session_key:
        return
    _COMMITTEE_MANAGEMENT_SESSIONS.pop(session_key, None)
