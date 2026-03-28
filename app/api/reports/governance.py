#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 10:30:15 2026

@author: anonymous
"""

import json
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_read_db
from app.channels.core.audit_security import decrypt_from_audit_store
from app.config import settings
from app.db.models import (
    ChannelMessageEvent,
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    MemberIdentity,
    Society,
    UserFlatMapping,
)
from app.utils.response import error_envelope
from app.api.reports.common import authorize_committee_member_report, record_report_access

from app.modules.reports.governance.audit_report import GovernanceAuditReport
from app.modules.reports.pdf.governance_audit_pdf import generate_governance_audit_pdf
from app.modules.reports.common.exporters import export_csv, export_excel

router = APIRouter(prefix="/reports/governance", tags=["Reports | Governance"])


def _society_identity_tokens(db: Session, *, society_id) -> set[str]:
    tokens: set[str] = set()

    committee_members = (
        db.query(CommitteeMember.phone_number)
        .filter(CommitteeMember.society_id == society_id)
        .all()
    )
    for (phone_number,) in committee_members:
        if phone_number:
            tokens.add(str(phone_number))

    committee_channel_ids = (
        db.query(CommitteeMemberChannelIdentity.external_user_id)
        .join(CommitteeMember, CommitteeMember.id == CommitteeMemberChannelIdentity.committee_member_id)
        .filter(CommitteeMember.society_id == society_id)
        .all()
    )
    for (external_user_id,) in committee_channel_ids:
        if external_user_id:
            tokens.add(str(external_user_id))

    resident_identities = (
        db.query(
            MemberIdentity.normalized_identifier,
            MemberIdentity.normalized_phone,
            MemberIdentity.whatsapp_user_id,
            MemberIdentity.telegram_user_id,
        )
        .join(UserFlatMapping, UserFlatMapping.member_identity_id == MemberIdentity.id)
        .filter(UserFlatMapping.society_id == society_id, UserFlatMapping.is_active.is_(True))
        .all()
    )
    for row in resident_identities:
        for value in row:
            if value:
                tokens.add(str(value))

    return tokens

@router.get("/audit/export")
def export_governance_audit(
    phone: str = Query(...),
    format: str = Query(default="csv"),
    db: Session = Depends(get_read_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="GOVERNANCE_AUDIT",
        log_message="Failed to authorize governance audit export",
    )
    if error_response:
        return error_response

    society = db.query(Society).get(member.society_id)
    if society is None:
        return error_envelope("Society not found")
    report = GovernanceAuditReport.generate(db, society.id)

    record_report_access(
        db=db,
        member=member,
        report_code="GOVERNANCE_AUDIT",
        format=format,
        society_id=society.id,
    )

    if format == "csv":
        return Response(
            export_csv(report["headers"], report["rows"]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=governance_audit.csv"}
        )

    if format == "excel":
        return Response(
            export_excel(
                sheet_name="Governance Audit",
                headers=report["headers"],
                rows=report["rows"]
            ),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=governance_audit.xlsx"}
        )

    if format == "pdf":
        branding = cast(dict[str, Any], (society.config_json or {}).get("branding", {}))
        logo_path = branding.get("logo_path")

        return Response(
            generate_governance_audit_pdf(
                society_name=society.name,
                report=report,
                logo_path=logo_path
            ),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=governance_audit.pdf"}
        )

    return error_envelope("Supported formats: csv, excel, pdf")


@router.get("/audit/events")
def read_protected_audit_events(
    phone: str = Query(...),
    channel: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_read_db),
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="GOVERNANCE_AUDIT",
        log_message="Failed to authorize secure audit read",
    )
    if error_response:
        return error_response

    role = (member.role or "").strip().lower()
    if role not in settings.AUDIT_READ_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for secure audit read")

    record_report_access(
        db=db,
        member=member,
        report_code="GOVERNANCE_AUDIT",
        format=(
            f"json; channel={channel or 'all'}; "
            f"event_type={event_type or 'all'}; "
            f"limit={limit}"
        ),
        society_id=member.society_id,
    )

    identity_tokens = _society_identity_tokens(db, society_id=member.society_id)
    query = db.query(ChannelMessageEvent)
    query = query.filter(
        or_(
            ChannelMessageEvent.society_id == member.society_id,
            ChannelMessageEvent.external_user_id.in_(identity_tokens),
            ChannelMessageEvent.chat_id_or_phone.in_(identity_tokens),
        )
    ).order_by(ChannelMessageEvent.occurred_at.desc())
    if channel:
        query = query.filter(ChannelMessageEvent.channel == channel)
    if event_type:
        query = query.filter(ChannelMessageEvent.event_type == event_type)

    rows = query.limit(limit).all()
    data = []
    for row in rows:
        row_message_text_raw_encrypted = cast(str | None, row.message_text_raw_encrypted)
        row_payload_json_encrypted = cast(str | None, row.payload_json_encrypted)
        payload_raw = None
        message_text_raw = None
        if settings.AUDIT_PII_CAPTURE_MODE == "encrypted_raw":
            message_text_raw = decrypt_from_audit_store(row_message_text_raw_encrypted)
            payload_decrypted = decrypt_from_audit_store(row_payload_json_encrypted)
            payload_raw = json.loads(payload_decrypted) if payload_decrypted else None

        data.append(
            {
                "id": str(row.id),
                "channel": row.channel,
                "direction": row.direction,
                "event_type": row.event_type,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                "message_text_redacted": row.message_text_redacted,
                "message_text_raw": message_text_raw,
                "payload_redacted": row.payload_json,
                "payload_json": payload_raw,
                "provider_error_code": row.provider_error_code,
                "provider_error_message": row.provider_error_message,
                "prev_event_hash": row.prev_event_hash,
                "event_hash": row.event_hash,
            }
        )

    return {
        "count": len(data),
        "retention_days_by_event": settings.AUDIT_RETENTION_DAYS_BY_EVENT,
        "pii_capture_mode": settings.AUDIT_PII_CAPTURE_MODE,
        "events": data,
    }
