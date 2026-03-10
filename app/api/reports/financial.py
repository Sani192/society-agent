#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:57:57 2026

@author: anonymous
"""

from fastapi import APIRouter, Depends, Query, Response
from typing import Any, cast
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Society
from app.modules.reports.financial.event_summary import EventFinancialSummaryReport
from app.modules.reports.financial.flat_payment_report import FlatPaymentReport
from app.modules.reports.financial.block_payment_report import BlockPaymentReport
from app.modules.reports.financial.sponsor_contribution_report import SponsorContributionReport
from app.modules.reports.financial.contribution_refund_report import ContributionRefundReport
from app.modules.reports.financial.balance_continuity_report import BalanceContinuityReport
from app.modules.reports.financial.member_refund_report import MemberRefundReport
from app.modules.reports.financial.ledger_report import LedgerReport
from app.modules.reports.common.exporters import export_csv, export_excel
from app.api.reports.common import (
    authorize_committee_member_report,
    record_report_access,
    require_event,
)
from app.modules.reports.pdf.flat_payment_pdf import generate_flat_payment_pdf
from app.modules.reports.pdf.block_payment_pdf import generate_block_payment_pdf
from app.modules.reports.pdf.event_financial_summary_pdf import generate_event_financial_summary_pdf
from app.modules.reports.pdf.sponsor_contribution_pdf import generate_sponsor_contribution_pdf
from app.modules.reports.pdf.contribution_refund_pdf import generate_contribution_refund_pdf
from app.modules.reports.pdf.balance_continuity_pdf import generate_balance_continuity_pdf
from app.modules.reports.pdf.member_refund_pdf import generate_member_refund_pdf
from app.modules.reports.pdf.ledger_pdf import generate_ledger_pdf
from app.utils.response import success, error_envelope



def _require_society(db: Session, society_id: int) -> Society:
    society = db.query(Society).get(society_id)
    if society is None:
        raise Exception("Society not found")
    return society


def _society_name(society: Society) -> str:
    return str(getattr(society, "name"))


def _society_logo_path(society: Society) -> str | None:
    config_json = cast(dict[str, Any] | None, getattr(society, "config_json"))
    branding = cast(dict[str, Any], (config_json or {}).get("branding") or {})
    logo_path = branding.get("logo_path")
    return str(logo_path) if logo_path else None
router = APIRouter(prefix="/reports/financial", tags=["Reports | Financial"])

@router.get("/event-summary")
def event_summary(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="EVENT_FINANCIAL_SUMMARY",
        log_message="Failed to authorize event financial summary report",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response
    
    data = EventFinancialSummaryReport.generate(db, event.id)
    
    record_report_access(
        db=db,
        member=member,
        report_code="EVENT_FINANCIAL_SUMMARY",
        format="JSON",
        event=event,
    )
    
    return success(data)


@router.get("/event-summary/export")
def export_event_financial_summary(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="EVENT_FINANCIAL_SUMMARY",
        log_message="Failed to authorize event financial summary export",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = EventFinancialSummaryReport.generate(db, event.id)
    
    record_report_access(
        db=db,
        member=member,
        report_code="EVENT_FINANCIAL_SUMMARY",
        format=format,
        event=event,
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
        society = _require_society(db, event.society_id)

        logo_path = _society_logo_path(society)

        pdf_data = generate_event_financial_summary_pdf(
            society_name=_society_name(society),
            event_name=event.name,
            summary=report,
            logo_path=logo_path or ""
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
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="FLAT_PAYMENTS",
        log_message="Failed to authorize flat payments report",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = FlatPaymentReport.generate(db, event.id)
    
    record_report_access(
        db=db,
        member=member,
        report_code="FLAT_PAYMENTS",
        format="JSON",
        event=event,
    )
    
    return success(report)


@router.get("/flat-payments/export")
def export_flat_payment_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="FLAT_PAYMENTS",
        log_message="Failed to authorize flat payments export",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = FlatPaymentReport.generate(db, event.id)
    
    record_report_access(
        db=db,
        member=member,
        report_code="FLAT_PAYMENTS",
        format=format,
        event=event,
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
        society = _require_society(db, event.society_id)

        logo_path = _society_logo_path(society)

        pdf_data = generate_flat_payment_pdf(
            society_name=_society_name(society),
            event_name=event.name,
            headers=report["headers"],
            rows=report["rows"],
            logo_path=logo_path or ""
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
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="BLOCK_PAYMENTS",
        log_message="Failed to authorize block payments report",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = BlockPaymentReport.generate(db, event.id)
    
    record_report_access(
        db=db,
        member=member,
        report_code="BLOCK_PAYMENTS",
        format="JSON",
        event=event,
    )
    
    return success(report)


@router.get("/block-payments/export")
def export_block_payment_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="BLOCK_PAYMENTS",
        log_message="Failed to authorize block payments export",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response
    
    report = BlockPaymentReport.generate(db, event.id)

    record_report_access(
        db=db,
        member=member,
        report_code="BLOCK_PAYMENTS",
        format=format,
        event=event,
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
    
        society = _require_society(db, event.society_id)

        logo_path = _society_logo_path(society)
    
        pdf_data = generate_block_payment_pdf(
            society_name=_society_name(society),
            event_name=event.name,
            headers=report["headers"],
            rows=report["rows"],
            logo_path=logo_path or ""
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
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="SPONSOR_CONTRIBUTIONS",
        log_message="Failed to authorize sponsor contributions export",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = SponsorContributionReport.generate(db, event.id)

    record_report_access(
        db=db,
        member=member,
        report_code="SPONSOR_CONTRIBUTIONS",
        format=format,
        event=event,
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
        society = _require_society(db, event.society_id)
        logo_path = _society_logo_path(society)

        pdf_data = generate_sponsor_contribution_pdf(
            society_name=_society_name(society),
            event_name=event.name,
            report=report,
            logo_path=logo_path or ""
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
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="CONTRIBUTION_REFUNDS",
        log_message="Failed to authorize contribution refunds export",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = ContributionRefundReport.generate(db, event.id)

    record_report_access(
        db=db,
        member=member,
        report_code="CONTRIBUTION_REFUNDS",
        format=format,
        event=event,
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
        society = _require_society(db, event.society_id)

        logo_path = _society_logo_path(society)

        pdf_data = generate_contribution_refund_pdf(
            society_name=_society_name(society),
            event_name=event.name,
            report=report,
            logo_path=logo_path or ""
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
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="BALANCE_CONTINUITY",
        log_message="Failed to authorize balance continuity export",
    )
    if error_response:
        return error_response

    report = BalanceContinuityReport.generate(
        db=db,
        society_id=member.society_id
    )

    record_report_access(
        db=db,
        member=member,
        report_code="BALANCE_CONTINUITY",
        format=format,
        society_id=member.society_id,
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
        society = _require_society(db, member.society_id)
        logo_path = _society_logo_path(society)

        return Response(
            generate_balance_continuity_pdf(
                society_name=_society_name(society),
                report=report,
                logo_path=logo_path or ""
            ),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=balance_continuity.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")

@router.get("/member-refunds/export")
def export_member_refunds(
    phone: str = Query(...),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="MEMBER_REFUNDS",
        log_message="Failed to authorize member refunds export",
    )
    if error_response:
        return error_response
    
    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = MemberRefundReport.generate(
        db=db,
        event_id=event.id
    )

    record_report_access(
        db=db,
        member=member,
        report_code="MEMBER_REFUNDS",
        format=format,
        society_id=member.society_id,
    )

    if format == "csv":
        return Response(
            export_csv(report["headers"], report["rows"]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=member_refunds.csv"
            }
        )

    if format == "excel":
        return Response(
            export_excel(
                sheet_name="Member Refunds",
                headers=report["headers"],
                rows=report["rows"]
            ),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=member_refunds.xlsx"
            }
        )

    if format == "pdf":
        society = _require_society(db, member.society_id)
        logo_path = _society_logo_path(society)

        return Response(
            generate_member_refund_pdf(
                society_name=_society_name(society),
                event_name=event.name,
                report=report,
                logo_path=logo_path or ""
            ),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=member_refund.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")

@router.get("/ledger/export")
def export_ledger(
    phone: str = Query(...),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_db)
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="LEDGER",
        log_message="Failed to authorize ledger export",
    )
    if error_response:
        return error_response
    
    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = LedgerReport.generate(
        db=db,
        event_id=event.id,
        society_id=member.society_id
    )

    record_report_access(
        db=db,
        member=member,
        report_code="LEDGER",
        format=format,
        society_id=member.society_id,
    )

    if format == "csv":
        return Response(
            export_csv(report["headers"], report["rows"]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=ledger_{event.name}.csv"
            }
        )

    if format == "excel":
        return Response(
            export_excel(
                sheet_name="Ledger",
                headers=report["headers"],
                rows=report["rows"]
            ),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=ledger_{event.name}.xlsx"
            }
        )

    if format == "pdf":
        society = _require_society(db, member.society_id)
        logo_path = _society_logo_path(society)

        return Response(
            generate_ledger_pdf(
                society_name=_society_name(society),
                event_name=event.name,
                report=report,
                logo_path=logo_path or ""
            ),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=ledger_{event.name}.pdf"
            }
        )

    return error_envelope("Supported formats: csv, excel, pdf")
