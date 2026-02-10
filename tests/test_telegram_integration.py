import asyncio

from app.api.telegram import telegram_webhook_event
from app.channels.telegram.adapter import parse_webhook_payload


class StubRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return self._payload


def _build_text_update(*, text: str = "help") -> dict:
    return {
        "update_id": 1001,
        "message": {
            "message_id": 55,
            "date": 1737000000,
            "text": text,
            "chat": {"id": 123456, "type": "private"},
            "from": {
                "id": 999,
                "first_name": "Jane",
                "last_name": "Doe",
                "username": "janed",
            },
        },
    }


def test_parse_telegram_webhook_payload_extracts_text_chat_and_user_info():
    inbound_messages = parse_webhook_payload(_build_text_update(text="my status"))

    assert len(inbound_messages) == 1
    inbound = inbound_messages[0]
    assert inbound.channel == "telegram"
    assert inbound.sender_id == "999"
    assert inbound.display_name == "Jane Doe"
    assert inbound.text == "my status"
    assert inbound.metadata["chat_id"] == "123456"
    assert inbound.metadata["message_id"] == 55
    assert inbound.metadata["update_id"] == 1001
    assert inbound.metadata["username"] == "janed"
    assert inbound.metadata["canonical_sender_id"] == "999"


def test_parse_telegram_webhook_payload_ignores_non_text_update():
    payload = {
        "update_id": 1002,
        "message": {
            "message_id": 56,
            "chat": {"id": 123456, "type": "private"},
            "from": {"id": 999, "first_name": "Jane"},
            "photo": [{"file_id": "abc"}],
        },
    }

    assert parse_webhook_payload(payload) == []


def test_telegram_webhook_event_uses_shared_handler_and_sends_reply(monkeypatch):
    sent_messages: list[tuple[str, str]] = []

    class StubTelegramClient:
        def send_text_message(self, chat_id: str, text: str):
            sent_messages.append((chat_id, text))
            return {"ok": True}

    def fake_handle_inbound_message(inbound_message):
        assert inbound_message.channel == "telegram"
        assert inbound_message.sender_id == "999"
        assert inbound_message.text == "help"
        return "Here are commands"

    monkeypatch.setattr("app.api.telegram.get_telegram_client", lambda: StubTelegramClient())
    monkeypatch.setattr("app.api.telegram.handle_inbound_message", fake_handle_inbound_message)

    response = asyncio.run(telegram_webhook_event(StubRequest(_build_text_update())))

    assert response == {"status": "ok"}
    assert sent_messages == [("123456", "Here are commands")]


def test_telegram_webhook_event_returns_ignored_without_inbound_messages(monkeypatch):
    monkeypatch.setattr("app.api.telegram.get_telegram_client", lambda: None)

    response = asyncio.run(telegram_webhook_event(StubRequest({"update_id": 2001})))

    assert response == {"status": "ignored"}
