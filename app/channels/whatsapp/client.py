#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Cloud API client.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from app.channels.whatsapp.constants import (
    DEFAULT_WHATSAPP_API_VERSION,
    DEFAULT_WHATSAPP_GRAPH_BASE_URL,
    WHATSAPP_MESSAGES_PATH,
    WHATSAPP_MESSAGING_PRODUCT,
    WHATSAPP_REQUEST_TIMEOUT_SECONDS,
)
from app.config import settings
from app.utils.logger import logger


@dataclass(frozen=True)
class WhatsAppClient:
    access_token: str
    phone_number_id: str
    api_version: str = DEFAULT_WHATSAPP_API_VERSION
    graph_base_url: str = DEFAULT_WHATSAPP_GRAPH_BASE_URL

    def send_text_message(self, to_phone: str, body: str) -> dict:
        url = (
            f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/{WHATSAPP_MESSAGES_PATH}"
        )
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
        try:
            response = requests.post(
                url=url,
                json=payload,
                headers=headers,
                timeout=WHATSAPP_REQUEST_TIMEOUT_SECONDS,
            )
            logger.info(
                "Received WhatsApp API response",
                extra={"status_code": response.status_code, "to_phone": to_phone},
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            logger.exception(
                "Failed sending WhatsApp message",
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
    )
    logger.info(
        "WhatsApp client prepared",
        extra={
            "api_version": client.api_version,
            "graph_base_url": client.graph_base_url,
        },
    )
    return client
