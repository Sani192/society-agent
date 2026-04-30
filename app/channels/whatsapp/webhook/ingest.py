from __future__ import annotations

import json

from fastapi import HTTPException, Request, status

from app.api.contracts import WhatsAppWebhookPayload
from app.channels.core.types import InboundMessage
from app.channels.whatsapp.adapter import parse_webhook_payload
from app.config import settings


def parse_request_payload(request: Request, raw_body: bytes) -> dict:
    payload_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    payload = WhatsAppWebhookPayload.model_validate(payload_data)
    return payload.model_dump(exclude_none=True)


def ensure_body_size(request: Request, raw_body: bytes) -> None:
    max_body_bytes = max(1024, min(int(settings.WHATSAPP_WEBHOOK_MAX_BODY_BYTES), int(settings.PUBLIC_ENDPOINT_MAX_BODY_BYTES)))
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_body_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")
    if len(raw_body) > max_body_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")


def extract_inbound_messages(payload_dict: dict) -> list[InboundMessage]:
    return parse_webhook_payload(payload_dict)
