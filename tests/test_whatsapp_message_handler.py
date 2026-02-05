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

    assert response == "❓ Sorry, I didn’t understand this command."
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
