from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
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
    if not phone:
        return None, error_envelope("Phone is required for report access.")
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(role=str(member.role), report_code=report_code)
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

    try:
        log_report_access(
            db=db,
            society_id=society_id,
            event_id=event_id,
            report_code=report_code,
            performed_by=member.id,
            format=format,
        )
        db.commit()
    except Exception:
        logger.warning(
            "Report access audit write failed on current session; retrying with write session",
            extra={"report_code": report_code, "member_id": str(member.id)},
        )
        write_db = SessionLocal()
        try:
            log_report_access(
                db=write_db,
                society_id=society_id,
                event_id=event_id,
                report_code=report_code,
                performed_by=member.id,
                format=format,
            )
            write_db.commit()
        except Exception:
            write_db.rollback()
            logger.exception(
                "Failed to persist report access audit log",
                extra={"report_code": report_code, "member_id": str(member.id)},
            )
        finally:
            write_db.close()
