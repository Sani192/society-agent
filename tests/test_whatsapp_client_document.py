import json

from app.channels.whatsapp.client import WhatsAppClient


def test_send_document_message_builds_payload(monkeypatch):
    captured = {}

    class DummyResponse:
        status = 200

        def read(self):
            return b'{"messages":[{"id":"wamid.1"}]}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return DummyResponse()

    monkeypatch.setattr("app.channels.whatsapp.client.urlopen", fake_urlopen)

    client = WhatsAppClient(access_token="token", phone_number_id="123")
    response = client.send_document_message(
        to_phone="919999000000",
        media_id="media-123",
        filename="report.pdf",
        caption="Monthly report",
    )

    assert response["messages"][0]["id"] == "wamid.1"
    assert captured["method"] == "POST"
    assert captured["body"] == {
        "messaging_product": "whatsapp",
        "to": "919999000000",
        "type": "document",
        "document": {
            "id": "media-123",
            "filename": "report.pdf",
            "caption": "Monthly report",
        },
    }
