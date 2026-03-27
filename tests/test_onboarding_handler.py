from types import SimpleNamespace
from unittest.mock import MagicMock

from app.handlers.shared.onboarding import handle_onboarding_intent
from tests.constants import COMMITTEE_PHONE, MEMBER_PHONE


def test_onboarding_join_requires_args():
    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN",
        phone_number=MEMBER_PHONE,
        message="join",
        member=None
    )
    assert response == "❌ Example: join ABC123 A-101"


def test_onboarding_join_invalid_code(monkeypatch):
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.JoinCodeService.get_society_by_join_code",
        lambda *args, **kwargs: None
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN",
        phone_number=MEMBER_PHONE,
        message="join ABC123 A-101",
        member=None
    )

    assert response == "❌ Invalid join code."


def test_onboarding_join_auto_approved(monkeypatch):
    society = SimpleNamespace(id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.JoinCodeService.get_society_by_join_code",
        lambda *args, **kwargs: society
    )
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingService.start_onboarding",
        lambda **kwargs: "APPROVED"
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN",
        phone_number=MEMBER_PHONE,
        message="join ABC123 A-101",
        member=None
    )

    assert response == "✅ You are successfully added to the society."


def test_onboarding_join_pending(monkeypatch):
    society = SimpleNamespace(id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.JoinCodeService.get_society_by_join_code",
        lambda *args, **kwargs: society
    )
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingService.start_onboarding",
        lambda **kwargs: "REQ-003"
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN",
        phone_number=MEMBER_PHONE,
        message="join ABC123 A-101",
        member=None
    )

    assert "Request ID: *REQ-003*" in response


def test_onboarding_join_surfaces_error(monkeypatch):
    society = SimpleNamespace(id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.JoinCodeService.get_society_by_join_code",
        lambda *args, **kwargs: society
    )

    def fake_start_onboarding(**kwargs):
        raise Exception("You are already registered with this society.")

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingService.start_onboarding",
        fake_start_onboarding
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN",
        phone_number=MEMBER_PHONE,
        message="join ABC123 A-101",
        member=None
    )

    assert response == "❌ You are already registered with this society."


def test_onboarding_join_committee_for_phone(monkeypatch):
    society = SimpleNamespace(id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.JoinCodeService.get_society_by_join_code",
        lambda *args, **kwargs: society
    )

    captured = {}

    def fake_start_onboarding(**kwargs):
        captured["user_identifier"] = kwargs["user_identifier"]
        return "APPROVED"

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingService.start_onboarding",
        fake_start_onboarding
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN",
        phone_number=COMMITTEE_PHONE,
        message="join ABC123 A-101 phone 7777712345",
        member=member
    )

    assert captured["user_identifier"] == "7777712345"
    assert response.startswith("✅")


def test_onboarding_join_status(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.get_latest_event",
        lambda db: event
    )
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingQueryService.get_user_join_status",
        lambda **kwargs: "APPROVED"
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number=MEMBER_PHONE,
        message="join status",
        member=None
    )

    assert response == "✅ Your membership is approved."


def test_onboarding_join_status_pending(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.get_latest_event",
        lambda db: event
    )
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingQueryService.get_user_join_status",
        lambda **kwargs: "PENDING"
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number=MEMBER_PHONE,
        message="join status",
        member=None
    )

    assert "Your join request is pending approval." in response


def test_onboarding_join_status_not_found(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.get_latest_event",
        lambda db: event
    )
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingQueryService.get_user_join_status",
        lambda **kwargs: None
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number=MEMBER_PHONE,
        message="join status",
        member=None
    )

    assert response == "❌ You have not requested to join any society."


def test_onboarding_join_status_committee_for_phone(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.get_latest_event",
        lambda db: event
    )

    captured = {}

    def fake_status(**kwargs):
        captured["user_identifier"] = kwargs["user_identifier"]
        return "APPROVED"

    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingQueryService.get_user_join_status",
        fake_status
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number=COMMITTEE_PHONE,
        message="join status phone 7777712345",
        member=member
    )

    assert captured["user_identifier"] == "7777712345"
    assert response == "✅ Your membership is approved."


def test_onboarding_join_status_no_event(monkeypatch):
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.get_latest_event",
        lambda db: None
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number=MEMBER_PHONE,
        message="join status",
        member=None
    )

    assert response == "❌ No society context found."


def test_onboarding_join_status_approved_hindi(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.get_latest_event",
        lambda db: event
    )
    monkeypatch.setattr(
        "app.handlers.shared.onboarding.OnboardingQueryService.get_user_join_status",
        lambda **kwargs: "APPROVED"
    )

    response = handle_onboarding_intent(
        db=MagicMock(),
        intent="JOIN_STATUS",
        phone_number=MEMBER_PHONE,
        message="join status",
        member=None,
        lang="hi",
    )

    assert response == "✅ आपकी सदस्यता स्वीकृत है।"
