from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FinanceActionSessionState:
    pending_action: str | None = None
    event_id: str | None = None


_FINANCE_ACTION_SESSIONS: dict[str, FinanceActionSessionState] = {}


def build_finance_action_session_key(*, sender_id: str | None) -> str | None:
    return sender_id


def get_finance_action_session(session_key: str | None) -> FinanceActionSessionState | None:
    if not session_key:
        return None
    return _FINANCE_ACTION_SESSIONS.get(session_key)


def save_finance_action_session(session_key: str | None, state: FinanceActionSessionState) -> None:
    if not session_key:
        return
    _FINANCE_ACTION_SESSIONS[session_key] = state


def clear_finance_action_session(session_key: str | None) -> None:
    if not session_key:
        return
    _FINANCE_ACTION_SESSIONS.pop(session_key, None)
