from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
