from __future__ import annotations

from uuid import UUID

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth import AuthenticatedPrincipal
from app.db.models import CommitteeMember, CommitteeMemberChannelIdentity
from app.db.session import SessionLocal
from app.modules.reports.common.resolvers import get_event
from app.permissions.report_guard import ensure_report_access
from app.utils.audit_logger import log_report_access
from app.utils.logger import logger
from app.utils.response import error_envelope, safe_error_envelope
from app.utils.validation import ValidationError, validate_uuid


def _resolve_authenticated_committee_member(*, principal: AuthenticatedPrincipal, db: Session):
    if principal.committee_member_id is not None:
        return (
            db.query(CommitteeMember)
            .filter(
                CommitteeMember.id == principal.committee_member_id,
                CommitteeMember.is_active.is_(True),
            )
            .first()
        )

    if principal.channel_type and principal.external_user_id:
        identity = (
            db.query(CommitteeMemberChannelIdentity)
            .join(CommitteeMember, CommitteeMember.id == CommitteeMemberChannelIdentity.committee_member_id)
            .filter(
                CommitteeMemberChannelIdentity.channel_type == principal.channel_type,
                CommitteeMemberChannelIdentity.external_user_id == principal.external_user_id,
                CommitteeMember.is_active.is_(True),
            )
            .first()
        )
        if identity:
            return identity.committee_member

    return None


def authorize_committee_member_report(
    *,
    principal: AuthenticatedPrincipal,
    db: Session,
    report_code: str,
    log_message: str,
):
    try:
        member = _resolve_authenticated_committee_member(principal=principal, db=db)
        if not member:
            raise Exception("No active committee member found for principal")
        ensure_report_access(role=str(member.role), report_code=report_code)
    except Exception:
        logger.exception(log_message)
        return None, error_envelope("Unable to authorize report access.")
    return member, None


def require_event(*, db: Session, event_id: str | None):
    resolved_event_id: str | UUID | None = event_id
    if event_id is not None:
        try:
            resolved_event_id = validate_uuid(event_id, field_name="event_id")
        except ValidationError:
            return (
                None,
                JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=safe_error_envelope(),
                ),
            )

    event = get_event(db, resolved_event_id)
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
