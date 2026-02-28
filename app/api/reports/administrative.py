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
from app.utils.response import error_envelope
from app.api.reports.common import authorize_committee_member_report, record_report_access

from app.modules.reports.administrative.member_directory_report import MemberDirectoryReport
from app.modules.reports.administrative.onboarding_status_report import OnboardingStatusReport
from app.modules.reports.administrative.announcement_history_report import AnnouncementHistoryReport
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
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="MEMBER_DIRECTORY",
        log_message="Failed to authorize member directory export",
    )
    if error_response:
        return error_response

    society = db.query(Society).get(member.society_id)
    report = MemberDirectoryReport.generate(db, society.id)

    record_report_access(
        db=db,
        member=member,
        report_code="MEMBER_DIRECTORY",
        format=format,
        society_id=society.id,
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

    return error_envelope("Supported formats: csv, excel, pdf")

@router.get("/onboarding/export")
def export_onboarding_status(
    phone: str = Query(...),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="ONBOARDING_STATUS",
        log_message="Failed to authorize onboarding status export",
    )
    if error_response:
        return error_response

    society = db.query(Society).get(member.society_id)
    report = OnboardingStatusReport.generate(db, society.id)

    record_report_access(
        db=db,
        member=member,
        report_code="ONBOARDING_STATUS",
        format=format,
        society_id=society.id,
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

    return error_envelope("Supported formats: csv, excel, pdf")


@router.get("/announcements/export")
def export_announcement_history(
    phone: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="ANNOUNCEMENT_HISTORY",
        log_message="Failed to authorize announcement history export",
    )
    if error_response:
        return error_response

    society = db.query(Society).get(member.society_id)
    report = AnnouncementHistoryReport.generate(db, society.id)

    record_report_access(
        db=db,
        member=member,
        report_code="ANNOUNCEMENT_HISTORY",
        format=format,
        society_id=society.id,
    )

    if format == "csv":
        return Response(export_csv(report["headers"], report["rows"]), media_type="text/csv")

    if format == "excel":
        return Response(
            export_excel("Announcements", report["headers"], report["rows"]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return error_envelope("Supported formats: csv, excel")
