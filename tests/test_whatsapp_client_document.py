from app.channels.whatsapp.client import WhatsAppClient


def test_send_document_message_builds_payload(monkeypatch):
    captured = {}

    class DummyResponse:
        status_code = 200
        content = b'{"messages":[{"id":"wamid.1"}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"messages": [{"id": "wamid.1"}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["body"] = json
        return DummyResponse()

    monkeypatch.setattr("app.channels.whatsapp.client.requests.post", fake_post)

    client = WhatsAppClient(access_token="token", phone_number_id="123")
    response = client.send_document_message(
        to_phone="919999000000",
        media_id="media-123",
        filename="report.pdf",
        caption="Monthly report",
    )

    assert response["messages"][0]["id"] == "wamid.1"
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
