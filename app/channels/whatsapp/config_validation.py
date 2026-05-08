from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class WhatsAppConfigValidationResult:
    complete: bool
    missing_fields: tuple[str, ...]


def validate_whatsapp_config(*, require_verify_token: bool) -> WhatsAppConfigValidationResult:
    missing_fields: list[str] = []

    if not settings.WHATSAPP_APP_SECRET:
        missing_fields.append("WHATSAPP_APP_SECRET")
    if not settings.WHATSAPP_ACCESS_TOKEN:
        missing_fields.append("WHATSAPP_ACCESS_TOKEN")
    if not settings.WHATSAPP_PHONE_NUMBER_ID:
        missing_fields.append("WHATSAPP_PHONE_NUMBER_ID")
    if require_verify_token and not settings.WHATSAPP_VERIFY_TOKEN:
        missing_fields.append("WHATSAPP_VERIFY_TOKEN")

    return WhatsAppConfigValidationResult(
        complete=not missing_fields,
        missing_fields=tuple(missing_fields),
    )


def validate_whatsapp_runtime_config() -> WhatsAppConfigValidationResult:
    return validate_whatsapp_config(require_verify_token=False)


def validate_whatsapp_verification_config() -> WhatsAppConfigValidationResult:
    missing_fields: list[str] = []
    if not settings.WHATSAPP_VERIFY_TOKEN:
        missing_fields.append("WHATSAPP_VERIFY_TOKEN")

    return WhatsAppConfigValidationResult(
        complete=not missing_fields,
        missing_fields=tuple(missing_fields),
    )


def validate_whatsapp_startup_config() -> WhatsAppConfigValidationResult:
    missing_fields = list(validate_whatsapp_config(require_verify_token=True).missing_fields)
    if settings.WHATSAPP_WEBHOOK_MAX_BODY_BYTES <= 0:
        missing_fields.append("WHATSAPP_WEBHOOK_MAX_BODY_BYTES")
    if settings.WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS <= 0:
        missing_fields.append("WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS")
    if settings.WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS <= 0:
        missing_fields.append("WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS")
    if settings.WHATSAPP_SENDER_SPAM_WINDOW_SECONDS <= 0:
        missing_fields.append("WHATSAPP_SENDER_SPAM_WINDOW_SECONDS")
    if settings.WHATSAPP_SENDER_SPAM_MAX_MESSAGES <= 0:
        missing_fields.append("WHATSAPP_SENDER_SPAM_MAX_MESSAGES")
    if settings.WHATSAPP_WEBHOOK_MAX_BODY_BYTES > settings.PUBLIC_ENDPOINT_MAX_BODY_BYTES:
        missing_fields.append("WHATSAPP_WEBHOOK_MAX_BODY_BYTES<=PUBLIC_ENDPOINT_MAX_BODY_BYTES")
    return WhatsAppConfigValidationResult(complete=not missing_fields, missing_fields=tuple(missing_fields))
