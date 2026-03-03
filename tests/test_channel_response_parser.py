from app.utils.channel_response_parser import parse_provider_error


def test_parse_provider_error_whatsapp_graph_api_shape():
    parsed = parse_provider_error(
        channel="whatsapp",
        response_payload={
            "error": {
                "message": "(#131026) Message undeliverable",
                "type": "OAuthException",
                "code": 131026,
                "error_subcode": 2494073,
            }
        },
        response_status_code=400,
    )

    assert parsed["provider_error_code"] == "OAuthException:131026:2494073"
    assert parsed["provider_error_message"] == "(#131026) Message undeliverable"
    assert parsed["http_status"] == 400


def test_parse_provider_error_telegram_shape():
    parsed = parse_provider_error(
        channel="telegram",
        response_payload={"ok": False, "error_code": 403, "description": "Forbidden: bot blocked by the user"},
        response_status_code=200,
    )

    assert parsed["provider_error_code"] == "403"
    assert parsed["provider_error_message"] == "Forbidden: bot blocked by the user"
    assert parsed["http_status"] == 200
