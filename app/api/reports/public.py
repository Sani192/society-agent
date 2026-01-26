#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 11:12:26 2026

@author: anonymous
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Event, Society
from app.utils.response import error
from app.modules.reports.common.resolvers import get_event
from app.utils.guards import ensure_member_of_society
from app.modules.reports.public.public_event_summary_report import PublicEventSummaryReport
from app.modules.reports.pdf.public_event_summary_pdf import generate_public_event_summary_pdf

router = APIRouter(prefix="/reports/public", tags=["Reports | Public"])

@router.get("/event-summary/pdf")
def public_event_summary_pdf(
    phone: str = Query(...),
    event_id: str = Query(...),
    db: Session = Depends(get_db)
):
    event = get_event(db, event_id)
    if not event:
        return error("Event not found")
    
    try:
        ensure_member_of_society(phone, db, event.society_id)
    except Exception as e:
        return error(e)

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
