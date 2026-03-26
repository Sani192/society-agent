from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.i18n.catalog import translate
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_exportable_report_options,
)
from app.modules.reports.pdf.base import get_pdf_render_language
from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService


def test_export_rejects_unknown_report_key():
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1")

    with pytest.raises(ValueError, match="Invalid report for category"):
        WhatsAppReportExportService.export(
            db=MagicMock(),
            member=member,
            event=None,
            category="financial",
            report="unknown-report",
            format="pdf",
        )


def test_export_unknown_report_key_guidance_lists_valid_values():
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1")

    with pytest.raises(ValueError) as exc_info:
        WhatsAppReportExportService.export(
            db=MagicMock(),
            member=member,
            event=None,
            category="financial",
            report="unknown-report",
            format="pdf",
        )

    error_message = str(exc_info.value)
    assert "Invalid report for category 'financial'" in error_message
    assert "Valid report keys:" in error_message
    assert "event-summary" in error_message
    assert "Try: report options" in error_message


def test_export_blocks_unauthorized_role():
    member = SimpleNamespace(role="secretary", society_id="soc-1", id="member-1")

    with pytest.raises(Exception, match="not allowed"):
        WhatsAppReportExportService.export(
            db=MagicMock(),
            member=member,
            event=None,
            category="financial",
            report="event-summary",
            format="pdf",
        )


def test_export_csv_returns_bytes_payload(monkeypatch):
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.ensure_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.record_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.EventFinancialSummaryReport.generate",
        lambda db, event_id: {"headers": ["Flat", "Amount"], "rows": [["A-101", 100]]},
    )

    society = SimpleNamespace(name="Test Society")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = society

    result = WhatsAppReportExportService.export(
        db=db,
        member=member,
        event=event,
        category="financial",
        report="event-summary",
        format="csv",
    )

    assert result["format"] == "csv"
    assert isinstance(result["payload"], bytes)
    assert result["payload"] == b"Flat,Amount\r\nA-101,100\r\n"


def test_export_operations_food_pass_excel(monkeypatch):
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.ensure_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.record_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.FoodPassOperationsReport.generate",
        lambda **kwargs: {
            "headers": ["Flat", "Entitled"],
            "rows": [["A-101", 2]],
        },
    )

    result = WhatsAppReportExportService.export(
        db=MagicMock(),
        member=member,
        event=event,
        category="operations",
        report="food-pass",
        format="excel",
        event_id="event-1",
    )

    assert result["category"] == "operations"
    assert result["report"] == "food-pass"
    assert result["format"] == "excel"
    assert result["filename"] == "food_pass_operations.xlsx"
    assert isinstance(result["payload"], bytes)


def test_export_operations_food_pass_pdf(monkeypatch):
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.ensure_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.record_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.FoodPassOperationsReport.generate",
        lambda **kwargs: {
            "headers": ["Flat", "Entitled"],
            "rows": [["A-101", 2]],
            "summary": {"total_passes_generated": 2, "served_count": 1, "remaining_count": 1, "fallback_serve_count": 0},
        },
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.generate_food_pass_operations_pdf",
        lambda **kwargs: b"pdf-bytes",
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(name="Test Society")

    result = WhatsAppReportExportService.export(
        db=db,
        member=member,
        event=event,
        category="operations",
        report="food-pass",
        format="pdf",
        event_id="event-1",
    )

    assert result["category"] == "operations"
    assert result["report"] == "food-pass"
    assert result["format"] == "pdf"
    assert result["filename"] == "food_pass_operations.pdf"
    assert result["payload"] == b"pdf-bytes"


def test_exportable_report_options_localize_labels_for_member_language():
    registry = build_whatsapp_report_registry(
        handlers_by_code=WhatsAppReportExportService.handlers_by_report_code(),
    )

    options = list_exportable_report_options(
        registry=registry,
        role="chairman",
        lang="hi",
    )

    food_pass_option = next(option for option in options if option["command_key"] == "operations:food-pass")
    assert food_pass_option["label"] == "फूड पास संचालन"


def test_export_operations_food_pass_excel_uses_localized_sheet_label(monkeypatch):
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1", preferred_language="hi")
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.ensure_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.record_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.FoodPassOperationsReport.generate",
        lambda **kwargs: {
            "headers": ["Flat", "Entitled"],
            "rows": [["A-101", 2]],
        },
    )

    captured = {}

    def _fake_export_excel(sheet_name, headers, rows):
        captured["sheet_name"] = sheet_name
        captured["headers"] = headers
        captured["rows"] = rows
        return b"excel-bytes"

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.export_excel",
        _fake_export_excel,
    )

    result = WhatsAppReportExportService.export(
        db=MagicMock(),
        member=member,
        event=event,
        category="operations",
        report="food-pass",
        format="excel",
        event_id="event-1",
    )

    assert result["payload"] == b"excel-bytes"
    assert captured["sheet_name"] == "फूड पास संचालन"


def test_export_operations_food_pass_pdf_applies_localized_pdf_shell_language(monkeypatch):
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1", preferred_language="hi")
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.ensure_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.record_report_access",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.FoodPassOperationsReport.generate",
        lambda **kwargs: {
            "headers": ["Flat", "Entitled"],
            "rows": [["A-101", 2]],
            "summary": {"total_passes_generated": 2, "served_count": 1, "remaining_count": 1, "fallback_serve_count": 0},
        },
    )

    captured = {}

    def _fake_food_pass_pdf(**kwargs):
        lang = get_pdf_render_language()
        captured["lang"] = lang
        captured["generated_by"] = translate("report_exports.pdf.generated_by", lang)
        captured["confidential"] = translate("report_exports.pdf.confidential", lang)
        return b"pdf-bytes-localized"

    monkeypatch.setattr(
        "app.modules.reports.whatsapp_export_service.generate_food_pass_operations_pdf",
        _fake_food_pass_pdf,
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(name="Test Society")

    result = WhatsAppReportExportService.export(
        db=db,
        member=member,
        event=event,
        category="operations",
        report="food-pass",
        format="pdf",
        event_id="event-1",
    )

    assert result["payload"] == b"pdf-bytes-localized"
    assert captured["lang"] == "hi"
    assert captured["generated_by"] == "Society Agent द्वारा जनरेट किया गया"
    assert captured["confidential"] == "गोपनीय – केवल सोसायटी उपयोग हेतु"
