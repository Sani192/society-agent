from __future__ import annotations

import hashlib
import hmac
from typing import NoReturn

from fastapi import HTTPException, status

from app.channels.whatsapp.constants import WHATSAPP_SIGNATURE_HEADER
from app.config import settings
from app.utils.logger import logger
from app.utils.operational_metrics import increment_counter
from app.utils.security_logging import log_security_event


def raise_config_unavailable(*, context: str, missing_fields: tuple[str, ...]) -> NoReturn:
    increment_counter("whatsapp.webhook.config_failure")
    logger.error(
        "WhatsApp configuration is incomplete",
        extra={"event": "whatsapp_config_validation_failure", "context": context, "missing_fields": list(missing_fields)},
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"WhatsApp channel configuration is incomplete for {context}. Set: {', '.join(missing_fields)}",
    )


def verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    app_secret = settings.WHATSAPP_APP_SECRET
    if not app_secret:
        raise_config_unavailable(context="signature verification", missing_fields=("WHATSAPP_APP_SECRET",))
    if not signature_header:
        log_security_event(
            logger,
            event="unauthorized_access",
            action="verify_whatsapp_signature",
            resource_id="whatsapp_webhook",
            method=WHATSAPP_SIGNATURE_HEADER,
            result="denied",
            reason_code="SIGNATURE_MISSING",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature header")

    expected_signature = "sha256=" + hmac.new(app_secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        log_security_event(
            logger,
            event="invalid_token_check",
            action="verify_whatsapp_signature",
            resource_id="whatsapp_webhook",
            method=WHATSAPP_SIGNATURE_HEADER,
            result="denied",
            reason_code="SIGNATURE_INVALID",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
