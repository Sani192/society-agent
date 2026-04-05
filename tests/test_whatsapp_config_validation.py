import asyncio

import pytest
from fastapi import HTTPException

from app.api.health import whatsapp_readiness_check
from app.api.whatsapp.webhook import whatsapp_webhook_event, whatsapp_webhook_verify
from app.utils.operational_metrics import get_counter, increment_counter, reset_counters


class StubRequest:
    def __init__(self):
        self.headers = {"X-Hub-Signature-256": "sha256=test"}

    async def body(self):
        return b'{"entry": []}'

    async def json(self):
        return {"entry": []}


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_counters()


def test_whatsapp_readiness_reports_degraded_when_config_incomplete(monkeypatch):
    monkeypatch.setattr("app.api.health.settings.WHATSAPP_ENABLED", True)
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_APP_SECRET", None)
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_ACCESS_TOKEN", None)
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_PHONE_NUMBER_ID", "phone-id")

    response = whatsapp_readiness_check()

    assert response.status == "degraded"
    assert response.enabled is True
    assert response.channel == "whatsapp"
    assert response.components["outbound_config"] == "degraded"
    assert response.missing_fields == ["WHATSAPP_APP_SECRET", "WHATSAPP_ACCESS_TOKEN"]
    assert response.alerts["failed_sends"] == "ok"
    assert response.alerts["retries_scheduled"] == "ok"
    assert response.alerts["dlq_growth"] == "ok"


def test_whatsapp_readiness_runs_connectivity_check_when_enabled(monkeypatch):
    monkeypatch.setattr("app.api.health.settings.WHATSAPP_ENABLED", True)
    monkeypatch.setattr("app.api.health.settings.WHATSAPP_READINESS_MODE", "connectivity")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_APP_SECRET", "secret")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_VERIFY_TOKEN", "verify")
    monkeypatch.setattr("app.api.health.settings.WHATSAPP_ALERT_FAILED_SENDS_THRESHOLD", 1)

    class StubClient:
        def check_connectivity(self, *, timeout_seconds: int):
            assert timeout_seconds >= 1
            return False, "Provider connectivity check failed: Timeout"

    monkeypatch.setattr("app.api.health.get_whatsapp_client", lambda: StubClient())
    increment_counter("whatsapp.outbound.failed_sends")

    response = whatsapp_readiness_check()

    assert response.status == "degraded"
    assert response.components["webhook_auth"] == "ok"
    assert response.components["outbound_config"] == "degraded"
    assert response.alerts["failed_sends"].startswith("alert:")


def test_whatsapp_webhook_event_returns_503_with_actionable_detail_when_config_incomplete(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp.webhook.settings.WHATSAPP_ENABLED", True)
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_APP_SECRET", None)
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_PHONE_NUMBER_ID", None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(whatsapp_webhook_event(StubRequest()))

    assert exc_info.value.status_code == 503
    assert "configuration is incomplete" in str(exc_info.value.detail)
    assert "WHATSAPP_APP_SECRET" in str(exc_info.value.detail)
    assert "WHATSAPP_PHONE_NUMBER_ID" in str(exc_info.value.detail)
    assert get_counter("whatsapp.webhook.config_failure") == 1


def test_whatsapp_verify_returns_503_when_verify_token_missing(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp.webhook.settings.WHATSAPP_ENABLED", True)
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_APP_SECRET", "secret")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_ACCESS_TOKEN", "token")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_PHONE_NUMBER_ID", "phone-id")
    monkeypatch.setattr("app.channels.whatsapp.config_validation.settings.WHATSAPP_VERIFY_TOKEN", None)

    with pytest.raises(HTTPException) as exc_info:
        whatsapp_webhook_verify(
            hub_mode="subscribe",
            hub_challenge="abc",
            hub_verify_token="anything",
        )

    assert exc_info.value.status_code == 503
    assert "WHATSAPP_VERIFY_TOKEN" in str(exc_info.value.detail)
    assert get_counter("whatsapp.webhook.config_failure") == 1
