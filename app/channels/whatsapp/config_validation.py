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
