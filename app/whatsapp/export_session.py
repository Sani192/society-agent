from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExportSessionState:
    options: list[dict] = field(default_factory=list)
    current_page: int = 0
    selected_category: str | None = None
    selected_report: str | None = None
    report_format: str | None = None
    event_id: str | None = None
    event_options: list[dict] = field(default_factory=list)


_EXPORT_SESSIONS: dict[str, ExportSessionState] = {}


def build_export_session_key(*, member_id: str | None, sender_id: str | None) -> str | None:
    if member_id and sender_id:
        return f"{member_id}:{sender_id}"
    return member_id or sender_id


def get_export_session(session_key: str | None) -> ExportSessionState | None:
    if not session_key:
        return None
    return _EXPORT_SESSIONS.get(session_key)


def save_export_session(session_key: str | None, state: ExportSessionState) -> None:
    if not session_key:
        return
    _EXPORT_SESSIONS[session_key] = state


def clear_export_session(session_key: str | None) -> None:
    if not session_key:
        return
    _EXPORT_SESSIONS.pop(session_key, None)
