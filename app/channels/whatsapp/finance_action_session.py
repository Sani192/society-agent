from __future__ import annotations

from dataclasses import dataclass

from app.channels.whatsapp.session_repository import InMemorySessionRepository


@dataclass
class FinanceActionSessionState:
    pending_action: str | None = None
    event_id: str | None = None


_REPOSITORY: InMemorySessionRepository[FinanceActionSessionState] = InMemorySessionRepository()


def build_finance_action_session_key(*, sender_id: str | None) -> str | None:
    return sender_id


def get_finance_action_session(session_key: str | None) -> FinanceActionSessionState | None:
    return _REPOSITORY.get(session_key)


def save_finance_action_session(session_key: str | None, state: FinanceActionSessionState) -> None:
    _REPOSITORY.save(session_key, state)


def clear_finance_action_session(session_key: str | None) -> None:
    _REPOSITORY.clear(session_key)
