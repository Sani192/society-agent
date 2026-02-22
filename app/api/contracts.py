from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


API_SCHEMA_VERSION = "1.0.0"


class HealthResponse(BaseModel):
    status: Literal["ok"]
    message: str


class WebhookStatusResponse(BaseModel):
    status: Literal["ok", "ignored"]


class ErrorResponse(BaseModel):
    detail: str


class WhatsAppWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    object: str | None = None
    entry: list[dict[str, Any]] = Field(default_factory=list)


class TelegramWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    update_id: int
