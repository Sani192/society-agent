import asyncio
import importlib

import pytest
from fastapi import HTTPException

from app.api.telegram import telegram_webhook_event
from app.api.whatsapp.webhook import whatsapp_webhook_event


class StubRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return self._payload


def test_whatsapp_webhook_event_returns_503_when_channel_disabled(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp.webhook.settings.WHATSAPP_ENABLED", False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "WhatsApp channel is disabled"


def test_telegram_webhook_returns_503_when_channel_disabled(monkeypatch):
    monkeypatch.setattr("app.api.telegram.settings.TELEGRAM_ENABLED", False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(telegram_webhook_event(StubRequest({"update_id": 1001})))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Telegram channel is disabled"


def test_main_registers_channel_routers_conditionally(monkeypatch):
    import app.config as app_config
    import app.main as main_module

    monkeypatch.setattr(app_config.settings, "WHATSAPP_ENABLED", False)
    monkeypatch.setattr(app_config.settings, "TELEGRAM_ENABLED", True)

    reloaded_main = importlib.reload(main_module)
    route_paths = {route.path for route in reloaded_main.app.routes}

    assert "/telegram" in route_paths
    assert "/whatsapp" not in route_paths
