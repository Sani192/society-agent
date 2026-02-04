#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:57:57 2026

@author: anonymous
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Society
from app.modules.reports.financial.event_summary import EventFinancialSummaryReport
from app.modules.reports.financial.flat_payment_report import FlatPaymentReport
from app.modules.reports.financial.block_payment_report import BlockPaymentReport
from app.modules.reports.financial.sponsor_contribution_report import SponsorContributionReport
from app.modules.reports.financial.contribution_refund_report import ContributionRefundReport
from app.modules.reports.financial.balance_continuity_report import BalanceContinuityReport
from app.modules.reports.common.exporters import export_csv, export_excel
from app.modules.reports.common.resolvers import get_event
from app.modules.reports.pdf.flat_payment_pdf import generate_flat_payment_pdf
from app.modules.reports.pdf.block_payment_pdf import generate_block_payment_pdf
from app.modules.reports.pdf.event_financial_summary_pdf import generate_event_financial_summary_pdf
from app.modules.reports.pdf.sponsor_contribution_pdf import generate_sponsor_contribution_pdf
from app.modules.reports.pdf.contribution_refund_pdf import generate_contribution_refund_pdf
from app.modules.reports.pdf.balance_continuity_pdf import generate_balance_continuity_pdf
from app.utils.logger import logger
from app.utils.response import success, error_envelope
from app.permissions.report_guard import ensure_report_access
from app.utils.guards import ensure_committee_member
from app.utils.audit_logger import log_report_access

router = APIRouter(prefix="/reports/financial", tags=["Reports | Financial"])

@router.get("/event-summary")
def event_summary(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="EVENT_FINANCIAL_SUMMARY"
        )
    except Exception:
        logger.exception("Failed to authorize event financial summary report")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")
    
    data = EventFinancialSummaryReport.generate(db, event.id)
    
    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="EVENT_FINANCIAL_SUMMARY",
        performed_by=member.id,
        format="JSON"
    )
    
    return success(data)


@router.get("/event-summary/export")
def export_event_financial_summary(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="EVENT_FINANCIAL_SUMMARY"
        )
    except Exception:
        logger.exception("Failed to authorize event financial summary export")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")

    report = EventFinancialSummaryReport.generate(db, event.id)
    
    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="EVENT_FINANCIAL_SUMMARY",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        csv_data = export_csv(report["headers"], report["rows"])
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=event_financial_summary.csv"}
        )

    if format == "excel":
        excel_data = export_excel(
            sheet_name="Event Financial Summary",
            headers=report["headers"],
            rows=report["rows"]
        )
        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=event_financial_summary.xlsx"
            }
        )
    
    if format == "pdf":
        society = db.query(Society).get(event.society_id)

        branding = (society.config_json or {}).get("branding", {})
        logo_path = branding.get("logo_path")

        pdf_data = generate_event_financial_summary_pdf(
            society_name=society.name,
            event_name=event.name,
            summary=report,
            logo_path=logo_path
        )

        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=event_financial_summary.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")


@router.get("/flat-payments")
def flat_payment_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="FLAT_PAYMENTS"
        )
    except Exception:
        logger.exception("Failed to authorize flat payments report")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")

    report = FlatPaymentReport.generate(db, event.id)
    
    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="FLAT_PAYMENTS",
        performed_by=member.id,
        format="JSON"
    )
    
    return success(report)


@router.get("/flat-payments/export")
def export_flat_payment_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="FLAT_PAYMENTS"
        )
    except Exception:
        logger.exception("Failed to authorize flat payments export")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")

    report = FlatPaymentReport.generate(db, event.id)
    
    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="FLAT_PAYMENTS",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        csv_data = export_csv(report["headers"], report["rows"])
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=flat_payments.csv"}
        )

    if format == "excel":
        excel_data = export_excel(
            sheet_name="Flat Payments",
            headers=report["headers"],
            rows=report["rows"]
        )
        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=flat_payments.xlsx"
            }
        )
    
    if format == "pdf":
        society = db.query(Society).get(event.society_id)
        
        branding = (society.config_json or {}).get("branding", {})
        logo_path = branding.get("logo_path")

        pdf_data = generate_flat_payment_pdf(
            society_name=society.name,
            event_name=event.name,
            rows=report["rows"],
            logo_path=logo_path
        )
    
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=flat_payments.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")


@router.get("/block-payments")
def block_payment_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="BLOCK_PAYMENTS"
        )
    except Exception:
        logger.exception("Failed to authorize block payments report")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")

    report = BlockPaymentReport.generate(db, event.id)
    
    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="BLOCK_PAYMENTS",
        performed_by=member.id,
        format="JSON"
    )
    
    return success(report)


@router.get("/block-payments/export")
def export_block_payment_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="BLOCK_PAYMENTS"
        )
    except Exception:
        logger.exception("Failed to authorize block payments export")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")
    
    report = BlockPaymentReport.generate(db, event.id)

    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="BLOCK_PAYMENTS",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        csv_data = export_csv(report["headers"], report["rows"])
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=block_payments.csv"}
        )

    if format == "excel":
        excel_data = export_excel(
            sheet_name="Block Payments",
            headers=report["headers"],
            rows=report["rows"]
        )
        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=block_payments.xlsx"
            }
        )
    
    if format == "pdf":
        report = BlockPaymentReport.generate(db, event.id)
    
        society = db.query(Society).get(event.society_id)
    
        branding = (society.config_json or {}).get("branding", {})
        logo_path = branding.get("logo_path")
    
        pdf_data = generate_block_payment_pdf(
            society_name=society.name,
            event_name=event.name,
            rows=report["rows"],
            logo_path=logo_path
        )
    
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=block_payments.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")

@router.get("/sponsor-contributions/export")
def export_sponsor_contributions(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="SPONSOR_CONTRIBUTIONS"
        )
    except Exception:
        logger.exception("Failed to authorize sponsor contributions export")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")

    report = SponsorContributionReport.generate(db, event.id)

    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="SPONSOR_CONTRIBUTIONS",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        csv_data = export_csv(report["headers"], report["rows"])
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=sponsor_contributions.csv"}
        )

    if format == "excel":
        excel_data = export_excel(
            sheet_name="Sponsor Contributions",
            headers=report["headers"],
            rows=report["rows"]
        )
        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=sponsor_contributions.xlsx"
            }
        )

    if format == "pdf":
        society = db.query(Society).get(event.society_id)
        branding = (society.config_json or {}).get("branding", {})
        logo_path = branding.get("logo_path")

        pdf_data = generate_sponsor_contribution_pdf(
            society_name=society.name,
            event_name=event.name,
            report=report,
            logo_path=logo_path
        )

        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=sponsor_contributions.pdf"}
        )

    return error_envelope("Supported formats: csv, excel, pdf")

@router.get("/contribution-refunds/export")
def export_contribution_refunds(
    phone: str = Query(...),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="CONTRIBUTION_REFUNDS"
        )
    except Exception:
        logger.exception("Failed to authorize contribution refunds export")
        return error_envelope("Unable to authorize report access.")
    
    event = get_event(db, event_id)
    if not event:
        return error_envelope("Event not found")

    report = ContributionRefundReport.generate(db, event.id)

    log_report_access(
        db=db,
        society_id=event.society_id,
        event_id=event.id,
        report_code="CONTRIBUTION_REFUNDS",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        return Response(
            content=export_csv(report["headers"], report["rows"]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=contribution_refunds.csv"
            }
        )

    if format == "excel":
        return Response(
            content=export_excel(
                sheet_name="Contribution Refunds",
                headers=report["headers"],
                rows=report["rows"]
            ),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=contribution_refunds.xlsx"
            }
        )

    if format == "pdf":
        society = db.query(Society).get(event.society_id)

        branding = (society.config_json or {}).get("branding", {})
        logo_path = branding.get("logo_path")

        pdf_data = generate_contribution_refund_pdf(
            society_name=society.name,
            event_name=event.name,
            report=report,
            logo_path=logo_path
        )

        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=contribution_refunds.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")

@router.get("/balance-continuity/export")
def export_balance_continuity(
    phone: str = Query(...),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    try:
        member = ensure_committee_member(phone, db)
        ensure_report_access(
            role=member.role,
            report_code="BALANCE_CONTINUITY"
        )
    except Exception:
        logger.exception("Failed to authorize balance continuity export")
        return error_envelope("Unable to authorize report access.")

    report = BalanceContinuityReport.generate(
        db=db,
        society_id=member.society_id
    )

    log_report_access(
        db=db,
        society_id=member.society_id,
        event_id=None,
        report_code="BALANCE_CONTINUITY",
        performed_by=member.id,
        format=format
    )

    if format == "csv":
        return Response(
            export_csv(report["headers"], report["rows"]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=balance_continuity.csv"
            }
        )

    if format == "excel":
        return Response(
            export_excel(
                sheet_name="Balance Continuity",
                headers=report["headers"],
                rows=report["rows"]
            ),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=balance_continuity.xlsx"
            }
        )

    if format == "pdf":
        society = db.query(Society).get(member.society_id)
        branding = (society.config_json or {}).get("branding", {})
        logo_path = branding.get("logo_path")

        return Response(
            generate_balance_continuity_pdf(
                society_name=society.name,
                report=report,
                logo_path=logo_path
            ),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=balance_continuity.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")
