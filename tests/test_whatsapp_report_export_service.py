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
