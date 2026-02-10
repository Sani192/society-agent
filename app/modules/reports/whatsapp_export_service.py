#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from app.api.reports.common import record_report_access
from app.db.models import Event, Society
from app.modules.reports.administrative.onboarding_status_report import OnboardingStatusReport
from app.modules.reports.common.exporters import export_csv, export_excel
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    resolve_report_entry,
)
from app.modules.reports.financial.event_summary import EventFinancialSummaryReport
from app.modules.reports.governance.audit_report import GovernanceAuditReport
from app.modules.reports.pdf.event_financial_summary_pdf import generate_event_financial_summary_pdf
from app.modules.reports.pdf.governance_audit_pdf import generate_governance_audit_pdf
from app.modules.reports.pdf.onboarding_status_pdf import generate_onboarding_status_pdf
from app.permissions.report_guard import ensure_report_access


class WhatsAppReportExportService:
    """Generate report exports from WhatsApp command parameters."""

    @staticmethod
    def _resolve_event(db, *, fallback_event, requested_event_id):
        if requested_event_id:
            return db.query(Event).filter(Event.id == requested_event_id).first()
        return fallback_event

    @staticmethod
    def _export_financial(*, db, member, event, normalized_format, event_id):
        target_event = WhatsAppReportExportService._resolve_event(
            db,
            fallback_event=event,
            requested_event_id=event_id,
        )
        if not target_event:
            raise ValueError("No active event found. Please provide event id.")

        report_data = EventFinancialSummaryReport.generate(db, target_event.id)
        society = db.query(Society).filter(Society.id == target_event.society_id).first()
        society_name = society.name if society else "Society"

        if normalized_format == "csv":
            payload = export_csv(report_data["headers"], report_data["rows"])
        elif normalized_format == "excel":
            payload = export_excel("Event Financial Summary", report_data["headers"], report_data["rows"])
        else:
            payload = generate_event_financial_summary_pdf(
                society_name=society_name,
                event_name=target_event.name,
                summary=report_data,
                logo_path=None,
            )

        return {
            "category": "financial",
            "report": "event-summary",
            "format": normalized_format,
            "event_id": str(target_event.id),
            "row_count": len(report_data["rows"]),
            "filename": f"event_financial_summary.{ 'xlsx' if normalized_format == 'excel' else normalized_format}",
            "payload": payload,
            "event": target_event,
        }

    @staticmethod
    def _export_admin(*, db, member, normalized_format, **_kwargs):
        report_data = OnboardingStatusReport.generate(db, member.society_id)
        society = db.query(Society).filter(Society.id == member.society_id).first()
        society_name = society.name if society else "Society"

        if normalized_format == "csv":
            payload = export_csv(report_data["headers"], report_data["rows"])
        elif normalized_format == "excel":
            payload = export_excel("Onboarding", report_data["headers"], report_data["rows"])
        else:
            payload = generate_onboarding_status_pdf(
                society_name=society_name,
                report=report_data,
                logo_path=None,
            )

        return {
            "category": "admin",
            "report": "onboarding-status",
            "format": normalized_format,
            "event_id": None,
            "row_count": len(report_data["rows"]),
            "filename": f"onboarding_status.{ 'xlsx' if normalized_format == 'excel' else normalized_format}",
            "payload": payload,
            "event": None,
        }

    @staticmethod
    def _export_governance(*, db, member, normalized_format, **_kwargs):
        report_data = GovernanceAuditReport.generate(db, member.society_id)
        society = db.query(Society).filter(Society.id == member.society_id).first()
        society_name = society.name if society else "Society"

        if normalized_format == "csv":
            payload = export_csv(report_data["headers"], report_data["rows"])
        elif normalized_format == "excel":
            payload = export_excel("Governance Audit", report_data["headers"], report_data["rows"])
        else:
            payload = generate_governance_audit_pdf(
                society_name=society_name,
                report=report_data,
                logo_path=None,
            )

        return {
            "category": "governance",
            "report": "audit",
            "format": normalized_format,
            "event_id": None,
            "row_count": len(report_data["rows"]),
            "filename": f"governance_audit.{ 'xlsx' if normalized_format == 'excel' else normalized_format}",
            "payload": payload,
            "event": None,
        }

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
            financial_handler=WhatsAppReportExportService._export_financial,
            admin_handler=WhatsAppReportExportService._export_admin,
            governance_handler=WhatsAppReportExportService._export_governance,
        )
        command_key, entry = resolve_report_entry(
            registry=export_registry,
            category=category,
            report=report,
        )

        ensure_report_access(role=member.role, report_code=entry.report_code)

        if entry.requires_event_id and not event_id:
            raise ValueError("event_id is required for this report")

        handler_entry = entry
        result = handler_entry.handler(
            db=db,
            member=member,
            event=event,
            normalized_format=normalized_format,
            event_id=event_id,
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
