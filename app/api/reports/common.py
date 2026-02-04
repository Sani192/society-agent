from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.reports.common.resolvers import get_event
from app.permissions.report_guard import ensure_report_access
from app.utils.audit_logger import log_report_access
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.utils.response import error_envelope


def authorize_committee_member_report(
    *,
    phone: str | None,
    db: Session,
    report_code: str,
    log_message: str,
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(role=member.role, report_code=report_code)
    except Exception:
        logger.exception(log_message)
        return None, error_envelope("Unable to authorize report access.")
    return member, None


def require_event(*, db: Session, event_id: str | None):
    event = get_event(db, event_id)
    if not event:
        return None, error_envelope("Event not found")
    return event, None


def record_report_access(
    *,
    db: Session,
    member,
    report_code: str,
    format: str,
    event=None,
    society_id: str | None = None,
):
    event_id = None
    if event is not None:
        society_id = event.society_id
        event_id = event.id
    elif society_id is None:
        society_id = member.society_id

    log_report_access(
        db=db,
        society_id=society_id,
        event_id=event_id,
        report_code=report_code,
        performed_by=member.id,
        format=format,
    )
