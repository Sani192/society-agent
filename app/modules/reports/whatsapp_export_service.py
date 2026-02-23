#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from app.api.reports.common import record_report_access
from app.db.models import Event, Society
from app.modules.reports.administrative.member_directory_report import MemberDirectoryReport
from app.modules.reports.administrative.onboarding_status_report import OnboardingStatusReport
from app.modules.reports.common.exporters import export_csv, export_excel
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    resolve_report_entry,
)
from app.modules.reports.financial.balance_continuity_report import BalanceContinuityReport
from app.modules.reports.financial.block_payment_report import BlockPaymentReport
from app.modules.reports.financial.contribution_refund_report import ContributionRefundReport
from app.modules.reports.financial.event_summary import EventFinancialSummaryReport
from app.modules.reports.financial.flat_payment_report import FlatPaymentReport
from app.modules.reports.financial.ledger_report import LedgerReport
from app.modules.reports.financial.member_refund_report import MemberRefundReport
from app.modules.reports.financial.sponsor_contribution_report import SponsorContributionReport
from app.modules.reports.governance.audit_report import GovernanceAuditReport
from app.modules.reports.pdf.balance_continuity_pdf import generate_balance_continuity_pdf
from app.modules.reports.pdf.block_payment_pdf import generate_block_payment_pdf
from app.modules.reports.pdf.contribution_refund_pdf import generate_contribution_refund_pdf
from app.modules.reports.pdf.event_financial_summary_pdf import generate_event_financial_summary_pdf
from app.modules.reports.pdf.flat_payment_pdf import generate_flat_payment_pdf
from app.modules.reports.pdf.governance_audit_pdf import generate_governance_audit_pdf
from app.modules.reports.pdf.ledger_pdf import generate_ledger_pdf
from app.modules.reports.pdf.member_directory_pdf import generate_member_directory_pdf
from app.modules.reports.pdf.member_refund_pdf import generate_member_refund_pdf
from app.modules.reports.pdf.onboarding_status_pdf import generate_onboarding_status_pdf
from app.modules.reports.pdf.sponsor_contribution_pdf import generate_sponsor_contribution_pdf
from app.permissions.report_guard import ensure_report_access


class WhatsAppReportExportService:
    """Generate report exports from WhatsApp command parameters."""

    @staticmethod
    def handlers_by_report_code():
        return {
            "EVENT_FINANCIAL_SUMMARY": WhatsAppReportExportService._export_event_financial_summary,
            "FLAT_PAYMENTS": WhatsAppReportExportService._export_flat_payments,
            "BLOCK_PAYMENTS": WhatsAppReportExportService._export_block_payments,
            "SPONSOR_CONTRIBUTIONS": WhatsAppReportExportService._export_sponsor_contributions,
            "CONTRIBUTION_REFUNDS": WhatsAppReportExportService._export_contribution_refunds,
            "BALANCE_CONTINUITY": WhatsAppReportExportService._export_balance_continuity,
            "MEMBER_REFUNDS": WhatsAppReportExportService._export_member_refunds,
            "LEDGER": WhatsAppReportExportService._export_ledger,
            "MEMBER_DIRECTORY": WhatsAppReportExportService._export_member_directory,
            "ONBOARDING_STATUS": WhatsAppReportExportService._export_onboarding_status,
            "GOVERNANCE_AUDIT": WhatsAppReportExportService._export_governance_audit,
        }

    @staticmethod
    def _resolve_event(db, *, fallback_event, requested_event_id):
        if requested_event_id:
            fallback_event_id = getattr(fallback_event, "id", None)
            if fallback_event_id and str(fallback_event_id) == str(requested_event_id):
                return fallback_event
            return db.query(Event).filter(Event.id == requested_event_id).first()
        return fallback_event

    @staticmethod
    def _resolve_society(db, *, society_id):
        society = db.query(Society).filter(Society.id == society_id).first()
        return society, (society.name if society else "Society")

    @staticmethod
    def _render_tabular_export(*, normalized_format, report_data, excel_sheet_name, pdf_renderer):
        if normalized_format == "csv":
            return export_csv(report_data["headers"], report_data["rows"])
        if normalized_format == "excel":
            return export_excel(excel_sheet_name, report_data["headers"], report_data["rows"])
        return pdf_renderer(report_data)

    @staticmethod
    def _build_result(*, category, report, normalized_format, event, row_count, filename_stem, payload):
        extension = "xlsx" if normalized_format == "excel" else normalized_format
        return {
            "category": category,
            "report": report,
            "format": normalized_format,
            "event_id": str(event.id) if event else None,
            "event_name": event.name if event else "General",
            "row_count": row_count,
            "filename": f"{filename_stem}.{extension}",
            "payload": payload,
            "event": event,
        }

    @staticmethod
    def _require_event(*, db, fallback_event, event_id):
        target_event = WhatsAppReportExportService._resolve_event(
            db,
            fallback_event=fallback_event,
            requested_event_id=event_id,
        )
        if not target_event:
            raise ValueError("No active event found. Please provide event id.")
        return target_event

    @staticmethod
    def _export_event_financial_summary(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(
            db=db,
            fallback_event=event,
            event_id=event_id,
        )
        report_data = EventFinancialSummaryReport.generate(db, target_event.id)
        _society, society_name = WhatsAppReportExportService._resolve_society(
            db,
            society_id=target_event.society_id,
        )

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Event Financial Summary",
            pdf_renderer=lambda data: generate_event_financial_summary_pdf(
                society_name=society_name,
                event_name=target_event.name,
                summary=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="event-summary",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem="event_financial_summary",
            payload=payload,
        )

    @staticmethod
    def _export_flat_payments(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(db=db, fallback_event=event, event_id=event_id)
        report_data = FlatPaymentReport.generate(db, target_event.id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=target_event.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Flat Payments",
            pdf_renderer=lambda data: generate_flat_payment_pdf(
                society_name=society_name,
                event_name=target_event.name,
                headers=data["headers"],
                rows=data["rows"],
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="flat-payments",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem="flat_payments",
            payload=payload,
        )

    @staticmethod
    def _export_block_payments(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(db=db, fallback_event=event, event_id=event_id)
        report_data = BlockPaymentReport.generate(db, target_event.id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=target_event.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Block Payments",
            pdf_renderer=lambda data: generate_block_payment_pdf(
                society_name=society_name,
                event_name=target_event.name,
                headers=data["headers"],
                rows=data["rows"],
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="block-payments",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem="block_payments",
            payload=payload,
        )

    @staticmethod
    def _export_sponsor_contributions(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(db=db, fallback_event=event, event_id=event_id)
        report_data = SponsorContributionReport.generate(db, target_event.id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=target_event.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Sponsor Contributions",
            pdf_renderer=lambda data: generate_sponsor_contribution_pdf(
                society_name=society_name,
                event_name=target_event.name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="sponsor-contributions",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem="sponsor_contributions",
            payload=payload,
        )

    @staticmethod
    def _export_contribution_refunds(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(db=db, fallback_event=event, event_id=event_id)
        report_data = ContributionRefundReport.generate(db, target_event.id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=target_event.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Contribution Refunds",
            pdf_renderer=lambda data: generate_contribution_refund_pdf(
                society_name=society_name,
                event_name=target_event.name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="contribution-refunds",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem="contribution_refunds",
            payload=payload,
        )

    @staticmethod
    def _export_balance_continuity(*, db, member, event, normalized_format, event_id):
        report_data = BalanceContinuityReport.generate(db, member.society_id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=member.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Balance Continuity",
            pdf_renderer=lambda data: generate_balance_continuity_pdf(
                society_name=society_name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="balance-continuity",
            normalized_format=normalized_format,
            event=None,
            row_count=len(report_data["rows"]),
            filename_stem="balance_continuity",
            payload=payload,
        )

    @staticmethod
    def _export_member_refunds(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(db=db, fallback_event=event, event_id=event_id)
        report_data = MemberRefundReport.generate(db=db, event_id=target_event.id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=member.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Member Refunds",
            pdf_renderer=lambda data: generate_member_refund_pdf(
                society_name=society_name,
                event_name=target_event.name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="member-refunds",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem="member_refunds",
            payload=payload,
        )

    @staticmethod
    def _export_ledger(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._require_event(db=db, fallback_event=event, event_id=event_id)
        report_data = LedgerReport.generate(db=db, event_id=target_event.id, society_id=member.society_id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=member.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Ledger",
            pdf_renderer=lambda data: generate_ledger_pdf(
                society_name=society_name,
                event_name=target_event.name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="financial",
            report="ledger",
            normalized_format=normalized_format,
            event=target_event,
            row_count=len(report_data["rows"]),
            filename_stem=f"ledger_{target_event.name}",
            payload=payload,
        )

    @staticmethod
    def _export_member_directory(*, db, member, event, normalized_format, event_id):
        report_data = MemberDirectoryReport.generate(db, member.society_id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=member.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Members",
            pdf_renderer=lambda data: generate_member_directory_pdf(
                society_name=society_name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="admin",
            report="member-directory",
            normalized_format=normalized_format,
            event=None,
            row_count=len(report_data["rows"]),
            filename_stem="member_directory",
            payload=payload,
        )

    @staticmethod
    def _export_onboarding_status(*, db, member, event, normalized_format, event_id):
        report_data = OnboardingStatusReport.generate(db, member.society_id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=member.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Onboarding",
            pdf_renderer=lambda data: generate_onboarding_status_pdf(
                society_name=society_name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="admin",
            report="onboarding-status",
            normalized_format=normalized_format,
            event=None,
            row_count=len(report_data["rows"]),
            filename_stem="onboarding_status",
            payload=payload,
        )

    @staticmethod
    def _export_governance_audit(*, db, member, event, normalized_format, event_id):
        report_data = GovernanceAuditReport.generate(db, member.society_id)
        _society, society_name = WhatsAppReportExportService._resolve_society(db, society_id=member.society_id)

        payload = WhatsAppReportExportService._render_tabular_export(
            normalized_format=normalized_format,
            report_data=report_data,
            excel_sheet_name="Governance Audit",
            pdf_renderer=lambda data: generate_governance_audit_pdf(
                society_name=society_name,
                report=data,
                logo_path=None,
            ),
        )

        return WhatsAppReportExportService._build_result(
            category="governance",
            report="audit",
            normalized_format=normalized_format,
            event=None,
            row_count=len(report_data["rows"]),
            filename_stem="governance_audit",
            payload=payload,
        )

    @staticmethod
    def export(
        *,
        db,
        member,
        event,
        category: str,
        report: str,
        format: str,
        event_id: str | None = None,
    ):
        normalized_format = (format or "").strip().lower()

        if normalized_format not in {"csv", "excel", "pdf"}:
            raise ValueError("Supported formats: csv, excel, pdf")

        export_registry = build_whatsapp_report_registry(
            handlers_by_code=WhatsAppReportExportService.handlers_by_report_code(),
        )
        _command_key, entry = resolve_report_entry(
            registry=export_registry,
            category=category,
            report=report,
        )

        ensure_report_access(role=member.role, report_code=entry.report_code)

        resolved_event_id = event_id or getattr(event, "id", None)
        if entry.requires_event_id and not resolved_event_id:
            raise ValueError("event_id is required for this report")

        result = entry.handler(
            db=db,
            member=member,
            event=event,
            normalized_format=normalized_format,
            event_id=resolved_event_id,
        )

        record_report_access(
            db=db,
            member=member,
            report_code=entry.report_code,
            format=normalized_format,
            event=result.get("event"),
        )
        result.pop("event", None)
        result["report"] = entry.normalized_report
        return result
