#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Cloud API client.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from app.config import settings
from app.utils.logger import logger


@dataclass(frozen=True)
class WhatsAppClient:
    access_token: str
    phone_number_id: str
    api_version: str = "v22.0"
    graph_base_url: str = "https://graph.facebook.com"

    def send_text_message(self, to_phone: str, body: str) -> dict:
        url = (
            f"{self.graph_base_url}/{self.api_version}/{self.phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        logger.info(f"send message :: url = {url}")
        logger.info(f"send message :: data = {data}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            logger.exception("Failed sending WhatsApp message")
            raise


def get_whatsapp_client() -> WhatsAppClient:
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError("WhatsApp credentials are not configured")
    return WhatsAppClient(
        access_token=settings.WHATSAPP_ACCESS_TOKEN,
        phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
        api_version=settings.WHATSAPP_API_VERSION,
        graph_base_url=settings.WHATSAPP_GRAPH_BASE_URL,
    )
