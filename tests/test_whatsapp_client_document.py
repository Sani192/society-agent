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


def test_send_button_message_builds_payload(monkeypatch):
    captured = {}

    class DummyResponse:
        status_code = 200
        content = b'{"messages":[{"id":"wamid.4"}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"messages": [{"id": "wamid.4"}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["body"] = json
        return DummyResponse()

    monkeypatch.setattr("app.channels.whatsapp.client.requests.post", fake_post)

    client = WhatsAppClient(access_token="token", phone_number_id="123")
    response = client.send_button_message(
        to_phone="919999000000",
        header_text="Society Control Panel",
        body_text="Select a section",
        buttons=[
            {"type": "reply", "reply": {"id": "ui::my-account", "title": "My Account"}},
            {"type": "reply", "reply": {"id": "ui::society", "title": "Society"}},
        ],
    )

    assert response["messages"][0]["id"] == "wamid.4"
    assert captured["body"]["type"] == "interactive"
    assert captured["body"]["interactive"]["type"] == "button"
    assert captured["body"]["interactive"]["action"]["buttons"][0]["reply"]["id"] == "ui::my-account"


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


def test_send_template_message_builds_payload(monkeypatch):
    captured = {}

    class DummyResponse:
        status_code = 200
        content = b'{"messages":[{"id":"wamid.8"}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return {"messages": [{"id": "wamid.8"}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["body"] = json
        return DummyResponse()

    monkeypatch.setattr("app.channels.whatsapp.client.requests.post", fake_post)

    client = WhatsAppClient(access_token="token", phone_number_id="123")
    response = client.send_template_message(
        to_phone="919999000000",
        template_name="announcement_fallback",
        body_parameters=["Important update"],
    )

    assert response["messages"][0]["id"] == "wamid.8"
    assert captured["body"]["type"] == "template"
    assert captured["body"]["template"]["name"] == "announcement_fallback"


def test_send_text_message_raises_retryable_error_with_retry_after(monkeypatch):
    class DummyResponse:
        status_code = 429
        content = b'{"error":"rate limit"}'
        headers = {"Retry-After": "7"}

        def raise_for_status(self):
            import requests

            raise requests.HTTPError("429", response=self)

    monkeypatch.setattr(
        "app.channels.whatsapp.client.requests.post",
        lambda *args, **kwargs: DummyResponse(),
    )

    from app.channels.whatsapp.client import WhatsAppRetryableError

    client = WhatsAppClient(access_token="token", phone_number_id="123")

    try:
        client.send_text_message("919999000000", "Hello")
        assert False, "Expected WhatsAppRetryableError"
    except WhatsAppRetryableError as exc:
        assert exc.retry_after_seconds == 7.0
