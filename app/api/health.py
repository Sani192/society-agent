#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:31:26 2026

@author: anonymous
"""

# app/api/health.py

from fastapi import APIRouter

from app.api.contracts import HealthResponse, WhatsAppReadinessResponse
from app.channels.whatsapp.config_validation import validate_whatsapp_runtime_config
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", message="Society Agent running locally")


@router.get("/health/readiness/whatsapp", response_model=WhatsAppReadinessResponse)
def whatsapp_readiness_check() -> WhatsAppReadinessResponse:
    if not settings.WHATSAPP_ENABLED:
        return WhatsAppReadinessResponse(
            status="disabled",
            channel="whatsapp",
            enabled=False,
            message="WhatsApp channel is disabled",
        )

    validation = validate_whatsapp_runtime_config()
    if validation.complete:
        return WhatsAppReadinessResponse(
            status="ok",
            channel="whatsapp",
            enabled=True,
            message="WhatsApp channel is ready",
        )

    missing = list(validation.missing_fields)
    return WhatsAppReadinessResponse(
        status="degraded",
        channel="whatsapp",
        enabled=True,
        missing_fields=missing,
        message=(
            "WhatsApp channel configuration is incomplete. "
            f"Set the following env vars: {', '.join(missing)}"
        ),
    )
