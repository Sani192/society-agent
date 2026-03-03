#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Cloud API client.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from json import JSONDecodeError

import requests  # type: ignore[import-untyped]

from app.channels.whatsapp.constants import (
    DEFAULT_WHATSAPP_API_VERSION,
    DEFAULT_WHATSAPP_GRAPH_BASE_URL,
    WHATSAPP_MEDIA_PATH,
    WHATSAPP_MESSAGES_PATH,
    WHATSAPP_MESSAGING_PRODUCT,
    WHATSAPP_REQUEST_TIMEOUT_SECONDS,
)
from app.config import settings
from app.utils.channel_audit_service import AuditTransport
from app.utils.channel_response_parser import parse_provider_error
from app.utils.logger import logger


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class WhatsAppRetryableError(requests.HTTPError):
    """HTTP error wrapper with parsed retry metadata for backoff-aware callers."""

    def __init__(
        self,
        message: str,
        *,
        response: requests.Response,
        retry_after_seconds: float | None,
    ) -> None:
        super().__init__(message, response=response)
        self.retry_after_seconds = retry_after_seconds


def _parse_retry_after(retry_after_raw: str | None) -> float | None:
    if not retry_after_raw:
        return None

    retry_after_raw = retry_after_raw.strip()
    if not retry_after_raw:
        return None

    try:
        return max(float(retry_after_raw), 0.0)
    except ValueError:
        pass

    try:
        retry_at = datetime.strptime(retry_after_raw, "%a, %d %b %Y %H:%M:%S GMT")
        retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0)
    except ValueError:
        logger.warning("Could not parse Retry-After header", extra={"retry_after": retry_after_raw})
        return None


def _raise_for_whatsapp_response(response: requests.Response, *, operation: str, to_phone: str | None = None) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = response.status_code
        if status_code in RETRYABLE_STATUS_CODES:
            retry_after_seconds = _parse_retry_after(response.headers.get("Retry-After"))
            raise WhatsAppRetryableError(
                f"WhatsApp API retryable error: status={status_code}",
                response=response,
                retry_after_seconds=retry_after_seconds,
            ) from exc
        raise


def _extract_response_payload(response: requests.Response, *, context: dict) -> dict:
    if not response.content:
        return {}
    try:
        return response.json()
    except (JSONDecodeError, ValueError):
        logger.warning(
            "WhatsApp API response was not valid JSON",
            extra={
                **context,
                "status_code": response.status_code,
                "response_preview": response.text[:200],
            },
        )
        return {}


@dataclass(frozen=True)
class WhatsAppClient:
    access_token: str
    phone_number_id: str
    api_version: str = DEFAULT_WHATSAPP_API_VERSION
    graph_base_url: str = DEFAULT_WHATSAPP_GRAPH_BASE_URL
    audit_transport: AuditTransport | None = None

    def _audit(self) -> AuditTransport:
        return self.audit_transport or AuditTransport(channel="whatsapp")

    @staticmethod
    def _provider_message_id_from_payload(payload: dict) -> str | None:
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if isinstance(messages, list) and messages:
            message = messages[0]
            if isinstance(message, dict) and message.get("id"):
                return str(message.get("id"))
        return None

    def upload_media(self, *, file_bytes: bytes, filename: str, mime_type: str) -> str:
        url = f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MEDIA_PATH}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        logger.info(
            "Uploading WhatsApp media",
            extra={"document_name": filename, "mime_type": mime_type, "url": url},
        )
        try:
            response = requests.post(
                url,
                headers=headers,
                data={"messaging_product": WHATSAPP_MESSAGING_PRODUCT},
                files={"file": (filename, file_bytes, mime_type)},
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_whatsapp_response(response, operation="upload_media")
            payload = _extract_response_payload(
                response,
                context={"operation": "upload_media", "document_name": filename},
            )
            media_id = payload.get("id")
            if not media_id:
                raise ValueError("Media upload succeeded but media id missing")
            logger.info(
                "WhatsApp media upload completed",
                extra={"document_name": filename, "media_id": media_id, "status_code": response.status_code},
            )
            return media_id
        except (requests.RequestException, ValueError):
            logger.exception(
                "Failed uploading WhatsApp media",
                extra={"document_name": filename, "url": url},
            )
            raise

    def send_document_message(
        self,
        to_phone: str,
        media_id: str,
        filename: str,
        caption: str | None = None,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        url = f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MESSAGES_PATH}"
        document_payload = {"id": media_id, "filename": filename}
        if caption:
            document_payload["caption"] = caption

        payload = {
            "messaging_product": WHATSAPP_MESSAGING_PRODUCT,
            "to": to_phone,
            "type": "document",
            "document": document_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Sending WhatsApp document message",
            extra={
                "to_phone": to_phone,
                "document_name": filename,
                "message_type": "document",
            },
        )
        self._audit().log_send_attempt(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=to_phone,
            outbound_payload_metadata={"message_type": "document", "document_name": filename},
        )
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_whatsapp_response(response, operation="send_document_message", to_phone=to_phone)
            payload = _extract_response_payload(
                response,
                context={"operation": "send_document_message", "to_phone": to_phone},
            )
            parsed_error = parse_provider_error(
                channel="whatsapp",
                response_payload=payload,
                response_status_code=response.status_code,
            )
            self._audit().log_send_result(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                status_code=response.status_code,
                provider_message_id=self._provider_message_id_from_payload(payload),
                response_payload_snapshot=payload,
                success=True,
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
            logger.info(
                "Received WhatsApp API response",
                extra={"status_code": response.status_code, "to_phone": to_phone, "message_type": "document"},
            )
            return payload
        except requests.RequestException as exc:
            self._audit().log_exception(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                exc=exc,
            )
            logger.exception(
                "Failed sending WhatsApp document message",
                extra={"to_phone": to_phone, "url": url, "document_name": filename},
            )
            raise

    def send_text_message(
        self,
        to_phone: str,
        body: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        url = f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MESSAGES_PATH}"
        payload = {
            "messaging_product": WHATSAPP_MESSAGING_PRODUCT,
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Sending WhatsApp message",
            extra={
                "to_phone": to_phone,
                "url": url,
                "message_type": "text",
            },
        )
        self._audit().log_send_attempt(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=to_phone,
            outbound_payload_metadata={"message_type": "text", "text_length": len(body)},
        )
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_whatsapp_response(response, operation="send_text_message", to_phone=to_phone)
            response_payload = _extract_response_payload(
                response,
                context={"operation": "send_text_message", "to_phone": to_phone},
            )
            parsed_error = parse_provider_error(
                channel="whatsapp",
                response_payload=response_payload,
                response_status_code=response.status_code,
            )
            self._audit().log_send_result(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                status_code=response.status_code,
                provider_message_id=self._provider_message_id_from_payload(response_payload),
                response_payload_snapshot=response_payload,
                success=True,
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
            logger.info(
                "Received WhatsApp API response",
                extra={"status_code": response.status_code, "to_phone": to_phone},
            )
            return response_payload
        except requests.RequestException as exc:
            self._audit().log_exception(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                exc=exc,
            )
            logger.exception(
                "Failed sending WhatsApp message",
                extra={"to_phone": to_phone, "url": url},
            )
            raise

    def send_template_message(
        self,
        *,
        to_phone: str,
        template_name: str,
        body_parameters: list[str] | None = None,
        language_code: str = "en",
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        url = f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MESSAGES_PATH}"
        template_payload: dict = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if body_parameters:
            template_payload["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in body_parameters],
                }
            ]

        payload = {
            "messaging_product": WHATSAPP_MESSAGING_PRODUCT,
            "to": to_phone,
            "type": "template",
            "template": template_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Sending WhatsApp template message",
            extra={"to_phone": to_phone, "url": url, "message_type": "template", "template_name": template_name},
        )
        self._audit().log_send_attempt(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=to_phone,
            outbound_payload_metadata={"message_type": "template", "template_name": template_name},
        )
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_whatsapp_response(response, operation="send_template_message", to_phone=to_phone)
            response_payload = _extract_response_payload(
                response,
                context={"operation": "send_template_message", "to_phone": to_phone},
            )
            parsed_error = parse_provider_error(
                channel="whatsapp",
                response_payload=response_payload,
                response_status_code=response.status_code,
            )
            self._audit().log_send_result(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                status_code=response.status_code,
                provider_message_id=self._provider_message_id_from_payload(response_payload),
                response_payload_snapshot=response_payload,
                success=True,
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
            logger.info(
                "Received WhatsApp API response",
                extra={"status_code": response.status_code, "to_phone": to_phone, "message_type": "template"},
            )
            return response_payload
        except requests.RequestException as exc:
            self._audit().log_exception(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                exc=exc,
            )
            logger.exception(
                "Failed sending WhatsApp template message",
                extra={"to_phone": to_phone, "url": url, "template_name": template_name},
            )
            raise

    def send_list_message(
        self,
        *,
        to_phone: str,
        header_text: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        footer_text: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        url = f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MESSAGES_PATH}"
        interactive_payload = {
            "type": "list",
            "header": {"type": "text", "text": header_text},
            "body": {"text": body_text},
            "action": {"button": button_text, "sections": sections},
        }
        if footer_text:
            interactive_payload["footer"] = {"text": footer_text}

        payload = {
            "messaging_product": WHATSAPP_MESSAGING_PRODUCT,
            "to": to_phone,
            "type": "interactive",
            "interactive": interactive_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Sending WhatsApp interactive list message",
            extra={"to_phone": to_phone, "url": url, "message_type": "interactive_list"},
        )
        self._audit().log_send_attempt(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=to_phone,
            outbound_payload_metadata={"message_type": "interactive_list", "sections": len(sections)},
        )
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_whatsapp_response(response, operation="send_list_message", to_phone=to_phone)
            payload = _extract_response_payload(
                response,
                context={"operation": "send_list_message", "to_phone": to_phone},
            )
            parsed_error = parse_provider_error(
                channel="whatsapp",
                response_payload=payload,
                response_status_code=response.status_code,
            )
            self._audit().log_send_result(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                status_code=response.status_code,
                provider_message_id=self._provider_message_id_from_payload(payload),
                response_payload_snapshot=payload,
                success=True,
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
            logger.info(
                "Received WhatsApp API response",
                extra={"status_code": response.status_code, "to_phone": to_phone, "message_type": "interactive_list"},
            )
            return payload
        except requests.RequestException as exc:
            self._audit().log_exception(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                exc=exc,
            )
            logger.exception(
                "Failed sending WhatsApp interactive list message",
                extra={"to_phone": to_phone, "url": url},
            )
            raise

    def send_button_message(
        self,
        *,
        to_phone: str,
        header_text: str,
        body_text: str,
        buttons: list[dict],
        footer_text: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        url = f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MESSAGES_PATH}"
        interactive_payload = {
            "type": "button",
            "header": {"type": "text", "text": header_text[:60]},
            "body": {"text": body_text[:1024]},
            "action": {"buttons": buttons[:3]},
        }
        if footer_text:
            interactive_payload["footer"] = {"text": footer_text[:60]}

        payload = {
            "messaging_product": WHATSAPP_MESSAGING_PRODUCT,
            "to": to_phone,
            "type": "interactive",
            "interactive": interactive_payload,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Sending WhatsApp interactive button message",
            extra={"to_phone": to_phone, "url": url, "message_type": "interactive_button"},
        )
        self._audit().log_send_attempt(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=to_phone,
            outbound_payload_metadata={"message_type": "interactive_button", "buttons": len(buttons)},
        )
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_whatsapp_response(response, operation="send_button_message", to_phone=to_phone)
            payload = _extract_response_payload(
                response,
                context={"operation": "send_button_message", "to_phone": to_phone},
            )
            parsed_error = parse_provider_error(
                channel="whatsapp",
                response_payload=payload,
                response_status_code=response.status_code,
            )
            self._audit().log_send_result(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                status_code=response.status_code,
                provider_message_id=self._provider_message_id_from_payload(payload),
                response_payload_snapshot=payload,
                success=True,
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
            logger.info(
                "Received WhatsApp API response",
                extra={"status_code": response.status_code, "to_phone": to_phone, "message_type": "interactive_button"},
            )
            return payload
        except requests.RequestException as exc:
            self._audit().log_exception(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=to_phone,
                exc=exc,
            )
            logger.exception(
                "Failed sending WhatsApp interactive button message",
                extra={"to_phone": to_phone, "url": url},
            )
            raise


def get_whatsapp_client() -> WhatsAppClient:
    logger.info("Preparing WhatsApp client")
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WhatsApp credentials are not configured")
        raise ValueError("WhatsApp credentials are not configured")

    client = WhatsAppClient(
        access_token=settings.WHATSAPP_ACCESS_TOKEN,
        phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
        api_version=settings.WHATSAPP_API_VERSION,
        graph_base_url=settings.WHATSAPP_GRAPH_BASE_URL,
        audit_transport=AuditTransport(channel="whatsapp"),
    )
    logger.info(
        "WhatsApp client prepared",
        extra={
            "api_version": client.api_version,
            "graph_base_url": client.graph_base_url,
        },
    )
    return client
