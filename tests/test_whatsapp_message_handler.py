from types import SimpleNamespace
from unittest.mock import MagicMock

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
