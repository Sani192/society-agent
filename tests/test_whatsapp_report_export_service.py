from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService


def test_export_rejects_unknown_report_key():
    member = SimpleNamespace(role="chairman", society_id="soc-1", id="member-1")

    with pytest.raises(ValueError, match="Unknown report key"):
        WhatsAppReportExportService.export(
            db=MagicMock(),
            member=member,
            event=None,
            category="financial",
            report="unknown-report",
            format="pdf",
        )


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
