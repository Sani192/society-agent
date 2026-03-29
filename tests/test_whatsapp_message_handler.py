from types import SimpleNamespace
from unittest.mock import MagicMock

import app.channels.core.handler as core_handler
import app.commands.router as commands_router
from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.channels.whatsapp.adapter import parse_webhook_payload
from app.channels.whatsapp.report_flow import _build_reports_list_sections
from app.channels.whatsapp.ui_router import WHATSAPP_MORE_REPORTS_ROW_ID, _chunk_report_options


def handle_message(phone_number: str, message: str, **overrides):
    inbound_message = InboundMessage(
        channel="whatsapp",
        sender_id=phone_number,
        display_name=phone_number,
        text=message,
        metadata={},
    )
    kwargs = {
        "session_factory": overrides.pop("session_factory", core_handler.SessionLocal),
        "committee_member_resolver": overrides.pop("committee_member_resolver", core_handler.ensure_committee_member),
        "latest_event_getter": overrides.pop("latest_event_getter", core_handler.get_latest_event_for_society),
        "intent_detector": overrides.pop("intent_detector", commands_router.detect_intent),
        "onboarding_intent_handler": overrides.pop("onboarding_intent_handler", core_handler.handle_onboarding_intent),
        "committee_intent_handler": overrides.pop("committee_intent_handler", core_handler.handle_committee_intent),
        "public_intent_handler": overrides.pop("public_intent_handler", core_handler.handle_public_intent),
    }
    kwargs.update(overrides)
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    return handle_inbound_message(inbound_message, **kwargs)


def test_handle_message_unknown_intent(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: SimpleNamespace(id="member-1")
    )
    monkeypatch.setattr("app.commands.router.detect_intent", lambda message, **kwargs: None)

    response = handle_message("999", "unknown")

    assert response == "ℹ️ Invalid option. Try a listed menu command. Use: menu, help, report options."
    db.close.assert_called_once()


def test_handle_message_onboarding_short_circuit(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: SimpleNamespace(id="member-1")
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: None)
    monkeypatch.setattr("app.commands.router.detect_intent", lambda message, **kwargs: "ONBOARD")

    onboarding_handler = MagicMock(return_value="✅ Onboarded")
    committee_handler = MagicMock(return_value=None)
    public_handler = MagicMock(return_value=None)

    monkeypatch.setattr(
        "app.channels.core.handler.handle_onboarding_intent",
        onboarding_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_committee_intent",
        committee_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_public_intent",
        public_handler
    )

    response = handle_message("999", "onboard")

    assert response == "✅ Onboarded"
    committee_handler.assert_not_called()
    public_handler.assert_not_called()
    db.close.assert_called_once()


def test_handle_message_routes_report_options_to_committee(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-1", role="chairman")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)
    monkeypatch.setattr("app.commands.router.detect_intent", lambda message, **kwargs: "REPORT_OPTIONS")

    onboarding_handler = MagicMock(return_value=None)
    committee_handler = MagicMock(return_value="✅ Report options")
    public_handler = MagicMock(return_value=None)

    monkeypatch.setattr(
        "app.channels.core.handler.handle_onboarding_intent",
        onboarding_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_committee_intent",
        committee_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_public_intent",
        public_handler
    )

    response = handle_message("999", "report options")

    assert response == "✅ Report options"
    committee_handler.assert_called_once()
    called_kwargs = committee_handler.call_args.kwargs
    assert called_kwargs["intent"] == "REPORT_OPTIONS"
    assert called_kwargs["member"] == member
    assert called_kwargs["event"] == event
    public_handler.assert_not_called()
    db.close.assert_called_once()


def test_export_session_list_options_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-1", name="Chair One", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    response = handle_message("919001", "report options")

    assert response.startswith("✅")
    assert "Choose report event + report" in response
    assert "🗂️ *Financial*" in response


def test_export_session_select_option_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-2", name="Chair Two", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    monkeypatch.setattr(
        "app.handlers.shared.committee.WhatsAppReportExportService.export",
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
        "app.handlers.shared.committee.get_whatsapp_client",
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

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    monkeypatch.setattr(
        "app.handlers.shared.committee.WhatsAppReportExportService.export",
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
        "app.handlers.shared.committee.get_whatsapp_client",
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

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    handle_message("919003", "report options")
    response = handle_message("919003", "export 99")

    assert response.startswith("❌")
    assert "Invalid selection" in response


def test_export_session_successful_export_dispatch_end_to_end(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-e2e-4", name="Chair Four", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    monkeypatch.setattr(
        "app.handlers.shared.committee.WhatsAppReportExportService.export",
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
        "app.handlers.shared.committee.get_whatsapp_client",
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


def test_build_reports_list_sections_paginates_without_dropping_options():
    options = []
    for idx in range(23):
        category = "financial" if idx < 8 else "governance"
        options.append(
            {
                "category": category,
                "command_key": f"{category}:report-{idx}",
                "label": f"Report {idx}",
            }
        )

    pages = _chunk_report_options(options, page_size=10)
    assert len(pages) == 3

    seen_ids = []
    for page_idx in range(len(pages)):
        sections = _build_reports_list_sections(options, page_index=page_idx)
        page_ids = [
            row["id"]
            for section in sections
            for row in section["rows"]
        ]
        assert len(page_ids) <= 10
        seen_ids.extend(page_ids)

    assert seen_ids == [f"export::{option['command_key']}" for option in options]


def test_build_reports_list_sections_includes_more_reports_action_row():
    options = [
        {
            "category": "financial",
            "command_key": f"financial:report-{idx}",
            "label": f"Report {idx}",
        }
        for idx in range(11)
    ]

    sections = _build_reports_list_sections(options, page_index=0, include_more_row=True)

    more_rows = [
        row
        for section in sections
        for row in section["rows"]
        if row["id"] == WHATSAPP_MORE_REPORTS_ROW_ID
    ]
    total_rows = sum(len(section["rows"]) for section in sections)

    assert len(more_rows) == 1
    assert more_rows[0]["title"] == "More reports"
    assert total_rows <= 10


def test_build_reports_list_sections_governance_entries_discoverable_across_pages():
    options = [
        {
            "category": "admin",
            "command_key": f"admin:report-{idx}",
            "label": f"Admin Report {idx}",
        }
        for idx in range(10)
    ]
    options.append(
        {
            "category": "governance",
            "command_key": "governance:audit",
            "label": "Governance Audit",
        }
    )

    first_page_sections = _build_reports_list_sections(options, page_index=0, include_more_row=True)
    second_page_sections = _build_reports_list_sections(options, page_index=1, include_more_row=True)

    first_page_ids = {
        row["id"] for section in first_page_sections for row in section["rows"]
    }
    second_page_ids = {
        row["id"] for section in second_page_sections for row in section["rows"]
    }

    assert "export::governance:audit" not in first_page_ids
    assert "export::governance:audit" in second_page_ids


def test_build_reports_list_sections_stable_page_order_for_future_reports():
    base_options = [
        {
            "category": "financial",
            "command_key": f"financial:report-{idx}",
            "label": f"Report {idx}",
        }
        for idx in range(13)
    ]

    page_one_before = _build_reports_list_sections(base_options, page_index=1)
    page_one_before_ids = [
        row["id"]
        for section in page_one_before
        for row in section["rows"]
    ]

    extended_options = base_options + [
        {
            "category": "governance",
            "command_key": "governance:audit",
            "label": "Governance Audit",
        },
        {
            "category": "governance",
            "command_key": "governance:meeting-minutes",
            "label": "Meeting Minutes",
        },
    ]

    page_one_after = _build_reports_list_sections(extended_options, page_index=1)
    page_one_after_ids = [
        row["id"]
        for section in page_one_after
        for row in section["rows"]
    ]

    assert page_one_after_ids[: len(page_one_before_ids)] == page_one_before_ids


def test_handle_message_link_member_is_not_supported_for_whatsapp(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db: (_ for _ in ()).throw(Exception("unauthorized"))
    )

    response = handle_message("919999000111", "link member ABC123")

    assert response == "ℹ️ Invalid option. That command is not available here. Use: menu, help."
    db.close.assert_called_once()


def test_handle_message_verify_phone_is_not_supported_for_whatsapp(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db: (_ for _ in ()).throw(Exception("unauthorized"))
    )

    response = handle_message("919999000112", "verify phone 9999000011")

    assert response == "ℹ️ Invalid option. That command is not available here. Use: menu, help."
    db.close.assert_called_once()


def test_handle_message_continues_event_wizard_without_intent(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-wizard", role="secretary", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member,
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: None)

    calls = []

    def fake_committee_handler(**kwargs):
        calls.append(kwargs)
        return "✅ continued"

    monkeypatch.setattr("app.channels.core.handler.handle_committee_intent", fake_committee_handler)

    from app.channels.whatsapp.event_creation_session import (
        EventCreationSessionState,
        build_event_creation_session_key,
        save_event_creation_session,
    )

    session_key = build_event_creation_session_key(member_id="member-wizard", sender_id="999")
    save_event_creation_session(session_key, EventCreationSessionState(step="event_date", name="Diwali"))

    monkeypatch.setattr("app.commands.router.detect_intent", lambda message, **kwargs: None)

    response = handle_message("999", "2026-11-01 19:00")

    assert response == "✅ continued"
    assert calls[0]["intent"] == "ADD_EVENT"


def test_activate_event_intent_to_event_service(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-activate", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-activate", name="Spring Fest", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member,
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    called = {}

    def fake_activate_event(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.EventService.activate_event",
        fake_activate_event,
    )

    response = handle_message("919011", "activate event")

    assert response.startswith("✅")
    assert "Event activated" in response
    assert called["event_id"] == "event-activate"
    assert called["performed_by"] == "member-activate"


def test_lock_passes_intent_to_event_service(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-lock", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-lock", name="Spring Fest", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member,
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    called = {}

    def fake_lock_passes(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.EventService.lock_passes",
        fake_lock_passes,
    )

    response = handle_message("919012", "lock passes")

    assert response.startswith("✅")
    assert "Passes locked" in response
    assert called["event_id"] == "event-lock"
    assert called["performed_by"] == "member-lock"


def test_start_event_intent_to_event_service(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-start", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-start", name="Spring Fest", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member,
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    called = {}

    def fake_start_event_day(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.EventService.start_event_day",
        fake_start_event_day,
    )

    response = handle_message("919013", "start event")

    assert response.startswith("✅")
    assert "Event day started" in response
    assert called["event_id"] == "event-start"
    assert called["performed_by"] == "member-start"


def test_add_sponsor_intent_to_contribution_service(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id="member-sponsor", role="chairman", society_id="soc-1")
    event = SimpleNamespace(id="event-sponsor", name="Spring Fest", society_id="soc-1")

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.channels.core.handler.ensure_committee_member",
        lambda phone, db, **kwargs: member,
    )
    monkeypatch.setattr("app.channels.core.handler.get_latest_event_for_society", lambda db, society_id: event)

    db.query.return_value.filter.return_value.first.return_value = None

    called = {}

    def fake_add_contribution(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.ContributionService.add_contribution",
        fake_add_contribution,
    )

    response = handle_message("919014", "add sponsor ABC Corp 5000")

    assert response.startswith("✅")
    assert "Sponsor added" in response
    assert called["event_id"] == "event-sponsor"
    assert called["performed_by"] == "member-sponsor"
    assert called["amount"] == 5000


def test_parse_webhook_payload_maps_timestamp_iso():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.456",
                                    "from": "919111222333",
                                    "timestamp": "1700000000",
                                    "text": {"body": "menu"},
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
    assert messages[0].metadata["timestamp"] == "1700000000"
    assert messages[0].metadata["timestamp_iso"] == "2023-11-14T22:13:20+00:00"
