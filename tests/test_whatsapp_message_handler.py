from types import SimpleNamespace
from unittest.mock import MagicMock

from app.channels.whatsapp.adapter import parse_webhook_payload
from app.whatsapp.handler import handle_message


def test_handle_message_unknown_intent(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db: SimpleNamespace(id="member-1")
    )
    monkeypatch.setattr("app.whatsapp.handler.detect_intent", lambda message: None)

    response = handle_message("999", "unknown")

    assert response == "ℹ️ Sorry, I didn’t understand this command."
    db.close.assert_called_once()


def test_handle_message_onboarding_short_circuit(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db: SimpleNamespace(id="member-1")
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: None)
    monkeypatch.setattr("app.whatsapp.handler.detect_intent", lambda message: "ONBOARD")

    onboarding_handler = MagicMock(return_value="✅ Onboarded")
    committee_handler = MagicMock(return_value=None)
    public_handler = MagicMock(return_value=None)

    monkeypatch.setattr(
        "app.whatsapp.handler.handle_onboarding_intent",
        onboarding_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_committee_intent",
        committee_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_public_intent",
        public_handler
    )

    response = handle_message("999", "onboard")

    assert response == "✅ Onboarded"
    committee_handler.assert_not_called()
    public_handler.assert_not_called()
    db.close.assert_called_once()


def test_handle_message_routes_export_command_to_committee(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-1", role="chairman")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: event)
    monkeypatch.setattr("app.whatsapp.handler.detect_intent", lambda message: "EXPORT_REPORT")

    onboarding_handler = MagicMock(return_value=None)
    committee_handler = MagicMock(return_value="✅ Export queued")
    public_handler = MagicMock(return_value=None)

    monkeypatch.setattr(
        "app.whatsapp.handler.handle_onboarding_intent",
        onboarding_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_committee_intent",
        committee_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_public_intent",
        public_handler
    )

    response = handle_message("999", "report export --category financial --report event-summary --format pdf")

    assert response == "✅ Export queued"
    committee_handler.assert_called_once()
    called_kwargs = committee_handler.call_args.kwargs
    assert called_kwargs["intent"] == "EXPORT_REPORT"
    assert called_kwargs["member"] == member
    assert called_kwargs["event"] == event
    public_handler.assert_not_called()
    db.close.assert_called_once()


def test_export_session_list_options_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-1", name="Chair One", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: event)

    response = handle_message("919001", "report options")

    assert response.startswith("✅")
    assert "Choose a report to export" in response
    assert "🗂️ *Financial*" in response


def test_export_session_select_option_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-2", name="Chair Two", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: event)

    monkeypatch.setattr(
        "app.commands.handlers.committee_handler.WhatsAppReportExportService.export",
        lambda **kwargs: {
            "category": "financial",
            "report": "event-summary",
            "format": "pdf",
            "event_id": "event-1",
            "event_name": "Spring Fest",
            "row_count": 5,
            "filename": "event_financial_summary.pdf",
            "payload": b"pdf-bytes",
        },
    )

    class DummyClient:
        def upload_media(self, **kwargs):
            return "media-123"

        def send_document_message(self, **kwargs):
            return {"messages": [{"id": "wamid.1"}]}

    monkeypatch.setattr(
        "app.commands.handlers.committee_handler.get_whatsapp_client",
        lambda: DummyClient(),
    )

    options_response = handle_message("919002", "report options")
    select_response = handle_message("919002", "export 1")

    assert options_response.startswith("✅")
    assert select_response.startswith("✅")
    assert "Report exported" in select_response


def test_export_session_select_option_by_number_only_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-2b", name="Chair Two B", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: event)

    monkeypatch.setattr(
        "app.commands.handlers.committee_handler.WhatsAppReportExportService.export",
        lambda **kwargs: {
            "category": "financial",
            "report": "event-summary",
            "format": "pdf",
            "event_id": "event-1",
            "event_name": "Spring Fest",
            "row_count": 5,
            "filename": "event_financial_summary.pdf",
            "payload": b"pdf-bytes",
        },
    )

    class DummyClient:
        def upload_media(self, **kwargs):
            return "media-123"

        def send_document_message(self, **kwargs):
            return {"messages": [{"id": "wamid.1"}]}

    monkeypatch.setattr(
        "app.commands.handlers.committee_handler.get_whatsapp_client",
        lambda: DummyClient(),
    )

    options_response = handle_message("919005", "report options")
    select_response = handle_message("919005", "1")

    assert options_response.startswith("✅")
    assert select_response.startswith("✅")
    assert "Report exported" in select_response


def test_export_session_invalid_selection_recovery_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-3", name="Chair Three", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: event)

    handle_message("919003", "report options")
    response = handle_message("919003", "export 99")

    assert response.startswith("❌")
    assert "Invalid report selection" in response


def test_export_session_successful_export_dispatch_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-4", name="Chair Four", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.whatsapp.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.whatsapp.handler.get_latest_event", lambda db: event)

    monkeypatch.setattr(
        "app.commands.handlers.committee_handler.WhatsAppReportExportService.export",
        lambda **kwargs: {
            "category": "financial",
            "report": "event-summary",
            "format": "pdf",
            "event_id": "event-1",
            "event_name": "Spring Fest",
            "row_count": 5,
            "filename": "event_financial_summary.pdf",
            "payload": b"pdf-bytes",
        },
    )

    sent = {}

    class DummyClient:
        def upload_media(self, **kwargs):
            sent["upload"] = kwargs
            return "media-123"

        def send_document_message(self, **kwargs):
            sent["send"] = kwargs
            return {"messages": [{"id": "wamid.1"}]}

    monkeypatch.setattr(
        "app.commands.handlers.committee_handler.get_whatsapp_client",
        lambda: DummyClient(),
    )

    handle_message("919004", "report options")
    response = handle_message("919004", "export 1")

    assert response.startswith("✅")
    assert "Report exported" in response
    assert "Generated by: Chair Four" in response
    assert "Event Name: Spring Fest" in response
    assert sent["send"]["to_phone"] == "919004"


def test_parse_webhook_payload_supports_interactive_list_reply():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "919999000000", "profile": {"name": "Alice"}}],
                            "messages": [
                                {
                                    "id": "wamid.123",
                                    "from": "919999000000",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {
                                            "id": "export::financial:ledger",
                                            "title": "Ledger",
                                        },
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    messages = parse_webhook_payload(payload)

    assert len(messages) == 1
    assert messages[0].text == "export::financial:ledger"
    assert messages[0].metadata["interactive_list_reply_title"] == "Ledger"
