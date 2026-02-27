from types import SimpleNamespace
from unittest.mock import MagicMock

from app.commands.handlers.onboarding_handler import handle_onboarding_intent as command_onboarding
from app.commands.handlers.public_handler import handle_public_intent as command_public
from app.whatsapp.handlers.onboarding_handler import handle_onboarding_intent as whatsapp_onboarding
from app.whatsapp.handlers.public_handler import handle_public_intent as whatsapp_public


def test_public_pay_amount_validation_matches_channels():
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    command_response = command_public(
        db=MagicMock(),
        intent="PAY",
        phone_number="9999999999",
        message="pay",
        event=event,
        member=None,
    )
    whatsapp_response = whatsapp_public(
        db=MagicMock(),
        intent="PAY",
        phone_number="9999999999",
        message="pay",
        event=event,
        member=None,
    )

    assert command_response == whatsapp_response


def test_public_help_matches_channels():
    command_response = command_public(
        db=MagicMock(),
        intent="HELP",
        phone_number="9999999999",
        message="help",
        event=None,
        member=None,
    )
    whatsapp_response = whatsapp_public(
        db=MagicMock(),
        intent="HELP",
        phone_number="9999999999",
        message="help",
        event=None,
        member=None,
    )

    assert command_response == whatsapp_response


def test_onboarding_join_status_no_society_context_matches_channels(monkeypatch):
    monkeypatch.setattr("app.handlers.shared.onboarding.resolve_sender_society_id", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.handlers.shared.onboarding.get_latest_event", lambda _db: None)

    command_response = command_onboarding(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number="9999999999",
        message="join status",
        member=None,
    )
    whatsapp_response = whatsapp_onboarding(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number="9999999999",
        message="join status",
        member=None,
    )

    assert command_response == whatsapp_response
