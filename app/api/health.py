#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:31:26 2026

@author: anonymous
"""

# app/api/health.py

from typing import Literal

from fastapi import APIRouter

from app.api.contracts import HealthResponse, WhatsAppReadinessResponse
from app.channels.whatsapp.client import get_whatsapp_client
from app.channels.whatsapp.config_validation import (
    validate_whatsapp_runtime_config,
    validate_whatsapp_verification_config,
)
from app.config import settings
from app.utils.operational_metrics import get_counter

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

    runtime_validation = validate_whatsapp_runtime_config()
    verification_validation = validate_whatsapp_verification_config()
    missing = list(runtime_validation.missing_fields)
    components: dict[str, str] = {}
    alerts: dict[str, str] = {}
    degraded_reasons: list[str] = []

    components["webhook_auth"] = "ok" if verification_validation.complete else "degraded"
    if not verification_validation.complete:
        degraded_reasons.append("Webhook verify token is missing")

    connectivity_mode = str(getattr(settings, "WHATSAPP_READINESS_MODE", "sanity")).strip().lower()
    connectivity_enabled = connectivity_mode == "connectivity"
    outbound_config_ready = runtime_validation.complete
    if runtime_validation.complete and connectivity_enabled:
        connectivity_ok, connectivity_message = get_whatsapp_client().check_connectivity(
            timeout_seconds=settings.WHATSAPP_CONNECTIVITY_TIMEOUT_SECONDS
        )
        outbound_config_ready = connectivity_ok
        if not connectivity_ok:
            degraded_reasons.append(connectivity_message)
    elif runtime_validation.complete:
        connectivity_message = "Outbound config sanity check passed"
    else:
        connectivity_message = "Outbound config missing required env vars"
        degraded_reasons.append(connectivity_message)
    components["outbound_config"] = "ok" if outbound_config_ready else "degraded"

    from app.api.whatsapp import webhook as whatsapp_webhook

    retry_queue_depth = len(whatsapp_webhook._RETRY_QUEUE)
    retry_queue_threshold = max(int(settings.WHATSAPP_ALERT_RETRY_QUEUE_DEPTH_THRESHOLD), 1)
    retry_worker_healthy = retry_queue_depth < retry_queue_threshold
    components["retry_worker"] = "ok" if retry_worker_healthy else "degraded"
    if not retry_worker_healthy:
        degraded_reasons.append(
            f"Retry queue depth {retry_queue_depth} is above threshold {retry_queue_threshold}"
        )

    failed_sends = get_counter("whatsapp.outbound.failed_sends")
    retries_scheduled = get_counter("whatsapp.webhook.retries_scheduled")
    dlq_growth = get_counter("whatsapp.dlq.growth")

    if failed_sends >= max(int(settings.WHATSAPP_ALERT_FAILED_SENDS_THRESHOLD), 1):
        alerts["failed_sends"] = (
            f"alert: failed sends {failed_sends} >= threshold "
            f"{settings.WHATSAPP_ALERT_FAILED_SENDS_THRESHOLD}"
        )
    else:
        alerts["failed_sends"] = "ok"

    if retries_scheduled >= max(int(settings.WHATSAPP_ALERT_RETRIES_SCHEDULED_THRESHOLD), 1):
        alerts["retries_scheduled"] = (
            f"alert: retries scheduled {retries_scheduled} >= threshold "
            f"{settings.WHATSAPP_ALERT_RETRIES_SCHEDULED_THRESHOLD}"
        )
    else:
        alerts["retries_scheduled"] = "ok"

    if dlq_growth >= max(int(settings.WHATSAPP_ALERT_DLQ_GROWTH_THRESHOLD), 1):
        alerts["dlq_growth"] = (
            f"alert: dlq growth {dlq_growth} >= threshold {settings.WHATSAPP_ALERT_DLQ_GROWTH_THRESHOLD}"
        )
    else:
        alerts["dlq_growth"] = "ok"

    status: Literal["ok", "degraded", "disabled"] = "ok"
    if missing or degraded_reasons or any(value != "ok" for value in alerts.values()):
        status = "degraded"
    message = "WhatsApp channel is ready"
    if status != "ok":
        message = "WhatsApp channel is degraded"

    return WhatsAppReadinessResponse(
        status=status,
        channel="whatsapp",
        enabled=True,
        components=components,
        alerts=alerts,
        missing_fields=missing,
        message=f"{message}. mode={connectivity_mode}. {connectivity_message}",
    )
