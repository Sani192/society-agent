from uuid import uuid4

import pytest

from app.db.models import AnnouncementDelivery
from app.modules.announcements.service import AnnouncementService


def test_build_whatsapp_template_payload_non_event():
    payload = AnnouncementService.build_whatsapp_template_payload(
        announcement_type="announcement",
        receiver_name="Asha",
        free_text="Maintenance planned",
        event_name=None,
    )

    assert payload["template_name"] == "society_announcement_general"
    assert payload["body_parameters"] == ["Asha", "Maintenance planned"]
    assert payload["app_language_code"] == "en"
    assert payload["template_locale_code"] == "en_US"


def test_build_whatsapp_template_payload_event():
    payload = AnnouncementService.build_whatsapp_template_payload(
        announcement_type="event",
        receiver_name="Asha",
        free_text="Starts at 7PM",
        event_name="Navratri",
    )

    assert payload["template_name"] == "society_announcement_event"
    assert payload["body_parameters"] == ["Asha", "Navratri", "Starts at 7PM"]
    assert payload["app_language_code"] == "en"
    assert payload["template_locale_code"] == "en_US"


@pytest.mark.parametrize(
    "kwargs,error",
    [
        (
            {
                "announcement_type": "announcement",
                "receiver_name": "",
                "free_text": "hello",
                "event_name": None,
            },
            "receiver_name is required",
        ),
        (
            {
                "announcement_type": "announcement",
                "receiver_name": "Asha",
                "free_text": "",
                "event_name": None,
            },
            "free_text is required",
        ),
        (
            {
                "announcement_type": "event",
                "receiver_name": "Asha",
                "free_text": "hello",
                "event_name": None,
            },
            "event_name is required",
        ),
    ],
)
def test_build_whatsapp_template_payload_validates_required_fields(kwargs, error):
    with pytest.raises(ValueError, match=error):
        AnnouncementService.build_whatsapp_template_payload(**kwargs)


def test_build_whatsapp_template_payload_validates_max_free_text_length():
    with pytest.raises(ValueError, match="exceeds max length"):
        AnnouncementService.build_whatsapp_template_payload(
            announcement_type="announcement",
            receiver_name="Asha",
            free_text="a" * (AnnouncementService.MAX_FREE_TEXT_LENGTH + 1),
            event_name=None,
        )


def test_create_announcement_persists_rendered_payload(db_session):
    society_id = uuid4()
    created_by = uuid4()
    member_identity_id = uuid4()

    db_session.flush.side_effect = None

    AnnouncementService.create_announcement(
        db_session,
        society_id=society_id,
        event_id=None,
        announcement_type="announcement",
        message_text="Water shutdown",
        created_by=created_by,
        recipients=[
            {
                "member_identity_id": member_identity_id,
                "channel": "whatsapp",
                "receiver_name": "Asha",
                "preferred_language": "en",
            }
        ],
    )

    deliveries = [
        call.args[0]
        for call in db_session.add.call_args_list
        if isinstance(call.args[0], AnnouncementDelivery)
    ]

    assert len(deliveries) == 1
    assert deliveries[0].rendered_payload == {
        "template_name": "society_announcement_general",
        "body_parameters": ["Asha", "Water shutdown"],
        "app_language_code": "en",
        "template_locale_code": "en_US",
    }


def test_build_whatsapp_template_payload_uses_recipient_language():
    payload = AnnouncementService.build_whatsapp_template_payload(
        announcement_type="announcement",
        receiver_name="Asha",
        free_text="Lift maintenance",
        event_name=None,
        app_language_code="hi",
    )

    assert payload["app_language_code"] == "hi"
    assert payload["template_locale_code"] == "hi_IN"


@pytest.mark.parametrize(
    "app_language_code,expected_locale",
    [
        ("en", "en_US"),
        ("hi", "hi_IN"),
        ("gu", "gu_IN"),
    ],
)
def test_build_whatsapp_template_payload_maps_supported_recipient_languages_to_locales(
    app_language_code,
    expected_locale,
):
    payload = AnnouncementService.build_whatsapp_template_payload(
        announcement_type="announcement",
        receiver_name="Asha",
        free_text="Lift maintenance",
        event_name=None,
        app_language_code=app_language_code,
    )

    assert payload["app_language_code"] == app_language_code
    assert payload["template_locale_code"] == expected_locale


@pytest.mark.parametrize("app_language_code", [None, "", "mr", "  xx  "])
def test_build_whatsapp_template_payload_falls_back_to_english_when_language_missing_or_unsupported(
    app_language_code,
):
    payload = AnnouncementService.build_whatsapp_template_payload(
        announcement_type="announcement",
        receiver_name="Asha",
        free_text="Lift maintenance",
        event_name=None,
        app_language_code=app_language_code,
    )

    assert payload["app_language_code"] == "en"
    assert payload["template_locale_code"] == "en_US"
