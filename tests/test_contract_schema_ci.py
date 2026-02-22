from __future__ import annotations

import json
from pathlib import Path

from app.api.contracts import API_SCHEMA_VERSION, TelegramWebhookPayload, WhatsAppWebhookPayload
from app.main import app


def _assert_backward_compatible(previous: dict, current: dict) -> None:
    for path, methods in previous.get("paths", {}).items():
        assert path in current.get("paths", {}), f"Removed path '{path}' requires a major contract version policy decision"
        for method in methods:
            assert method in current["paths"][path], (
                f"Removed operation '{method.upper()} {path}' is not backward compatible"
            )


def test_provider_contract_matches_or_is_versioned_and_backward_compatible():
    contract_path = Path("contracts/openapi.v1.json")
    expected = json.loads(contract_path.read_text())
    current = app.openapi()

    expected_version = expected["info"]["version"]
    current_version = current["info"]["version"]

    if current_version == expected_version:
        assert current == expected, (
            "OpenAPI contract drift detected without version bump. "
            "Regenerate contracts/openapi.v1.json or bump API_SCHEMA_VERSION with compatible changes."
        )
    else:
        _assert_backward_compatible(previous=expected, current=current)


def test_provider_and_consumer_use_same_schema_version():
    contract = json.loads(Path("contracts/openapi.v1.json").read_text())
    assert API_SCHEMA_VERSION == contract["info"]["version"]
    assert app.version == API_SCHEMA_VERSION


def test_consumer_payload_contracts_validate_against_shared_schemas():
    telegram_payload = {
        "update_id": 1001,
        "message": {
            "message_id": 55,
            "date": 1737000000,
            "text": "help",
            "chat": {"id": 123456, "type": "private"},
            "from": {"id": 999, "first_name": "Jane"},
        },
    }
    whatsapp_payload = {"object": "whatsapp_business_account", "entry": []}

    assert TelegramWebhookPayload.model_validate(telegram_payload)
    assert WhatsAppWebhookPayload.model_validate(whatsapp_payload)
