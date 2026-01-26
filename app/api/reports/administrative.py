#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:10:53 2026

@author: anonymous
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Society
from app.permissions.report_guard import ensure_report_access
from app.utils.audit_logger import log_report_access
from app.utils.guards import ensure_committee_member
from app.utils.response import error

from app.modules.reports.administrative.member_directory_report import MemberDirectoryReport
from app.modules.reports.administrative.onboarding_status_report import OnboardingStatusReport
from app.modules.reports.pdf.member_directory_pdf import generate_member_directory_pdf
from app.modules.reports.pdf.onboarding_status_pdf import generate_onboarding_status_pdf
from app.modules.reports.common.exporters import export_csv, export_excel

router = APIRouter(prefix="/reports/admin", tags=["Reports | Admin"])

@router.get("/members/export")
def export_member_directory(
    phone: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="MEMBER_DIRECTORY"
        )
    except Exception as e:
        return error(e)

    society = db.query(Society).get(member.society_id)
    report = MemberDirectoryReport.generate(db, society.id)

    log_report_access(
        db=db,
        society_id=society.id,
        event_id=None,
        report_code="MEMBER_DIRECTORY",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        return Response(export_csv(report["headers"], report["rows"]), media_type="text/csv")

    if format == "excel":
        return Response(
            export_excel("Members", report["headers"], report["rows"]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if format == "pdf":
        branding = (society.config_json or {}).get("branding", {})
        return Response(
            generate_member_directory_pdf(
                society_name=society.name,
                report=report,
                logo_path=branding.get("logo_path")
            ),
            media_type="application/pdf"
        )

    return error("Supported formats: csv, excel, pdf")

@router.get("/onboarding/export")
def export_onboarding_status(
    phone: str = Query(...),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="ONBOARDING_STATUS"
        )
    except Exception as e:
        return error(e)

    society = db.query(Society).get(member.society_id)
    report = OnboardingStatusReport.generate(db, society.id)

    log_report_access(
        db=db,
        society_id=society.id,
        event_id=None,
        report_code="ONBOARDING_STATUS",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        return Response(export_csv(report["headers"], report["rows"]), media_type="text/csv")

    if format == "excel":
        return Response(
            export_excel("Onboarding", report["headers"], report["rows"]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if format == "pdf":
        branding = (society.config_json or {}).get("branding", {})
        return Response(
            generate_onboarding_status_pdf(
                society_name=society.name,
                report=report,
                logo_path=branding.get("logo_path")
            ),
            media_type="application/pdf"
        )

    return error("Supported formats: csv, excel, pdf")
