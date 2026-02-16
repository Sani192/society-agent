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


def test_send_list_message_builds_payload(monkeypatch):
    captured = {}

    class DummyResponse:
        status_code = 200
        content = b'{"messages":[{"id":"wamid.2"}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"messages": [{"id": "wamid.2"}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["body"] = json
        return DummyResponse()

    monkeypatch.setattr("app.channels.whatsapp.client.requests.post", fake_post)

    client = WhatsAppClient(access_token="token", phone_number_id="123")
    response = client.send_list_message(
        to_phone="919999000000",
        header_text="Reports",
        body_text="Choose one",
        button_text="Open",
        sections=[
            {
                "title": "Financial",
                "rows": [{"id": "export::financial:ledger", "title": "Ledger"}],
            }
        ],
        footer_text="Tip",
    )

    assert response["messages"][0]["id"] == "wamid.2"
    assert captured["body"]["type"] == "interactive"
    assert captured["body"]["interactive"]["type"] == "list"
    assert captured["body"]["interactive"]["action"]["sections"][0]["rows"][0]["id"] == "export::financial:ledger"


def test_send_text_message_handles_non_json_response(monkeypatch):
    class DummyResponse:
        status_code = 200
        content = b"ok"
        text = "ok"

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(
        "app.channels.whatsapp.client.requests.post",
        lambda *args, **kwargs: DummyResponse(),
    )

    client = WhatsAppClient(access_token="token", phone_number_id="123")
    response = client.send_text_message("919999000000", "Hello")

    assert response == {}
