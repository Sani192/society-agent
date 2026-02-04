#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 26 10:30:15 2026

@author: anonymous
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Society
from app.permissions.report_guard import ensure_report_access
from app.utils.audit_logger import log_report_access
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.utils.response import error_envelope

from app.modules.reports.governance.audit_report import GovernanceAuditReport
from app.modules.reports.pdf.governance_audit_pdf import generate_governance_audit_pdf
from app.modules.reports.common.exporters import export_csv, export_excel

router = APIRouter(prefix="/reports/governance", tags=["Reports | Governance"])

@router.get("/audit/export")
def export_governance_audit(
    phone: str = Query(...),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="GOVERNANCE_AUDIT"
        )
    except Exception:
        logger.exception("Failed to authorize governance audit export")
        return error_envelope("Unable to authorize report access.")

    society = db.query(Society).get(member.society_id)
    report = GovernanceAuditReport.generate(db, society.id)

    log_report_access(
        db=db,
        society_id=society.id,
        event_id=None,
        report_code="GOVERNANCE_AUDIT",
        performed_by=member.id,
        format=format
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
        branding = (society.config_json or {}).get("branding", {})
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
