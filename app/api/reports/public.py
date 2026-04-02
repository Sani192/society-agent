#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 11:12:26 2026

@author: anonymous
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_read_db
from app.api.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.db.models import Society
from app.api.reports.common import require_event
from app.utils.logger import logger
from app.utils.response import error_envelope
from app.utils.guards import ensure_member_of_society
from app.modules.reports.public.public_event_summary_report import PublicEventSummaryReport
from app.modules.reports.pdf.public_event_summary_pdf import generate_public_event_summary_pdf

router = APIRouter(prefix="/reports/public", tags=["Reports | Public"])

@router.get("/event-summary/pdf")
def public_event_summary_pdf(
    event_id: str = Query(...),
    db: Session = Depends(get_read_db),
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
):
    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response
    
    identity_for_society_membership = principal.phone or principal.external_user_id
    if not identity_for_society_membership:
        return error_envelope("Unable to authorize report access.")

    try:
        ensure_member_of_society(identity_for_society_membership, db, event.society_id)
    except Exception:
        logger.exception("Failed to authorize public event summary export")
        return error_envelope("Unable to authorize report access.")

    society = db.query(Society).get(event.society_id)
    summary = PublicEventSummaryReport.generate(db, event.id)

    branding = (society.config_json or {}).get("branding", {})
    logo_path = branding.get("logo_path")

    return Response(
        generate_public_event_summary_pdf(
            society_name=society.name,
            event_name=event.name,
            summary=summary,
            logo_path=logo_path
        ),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=public_event_summary.pdf"
        }
    )
