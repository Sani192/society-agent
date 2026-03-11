#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Durable queue worker for announcement deliveries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import requests  # type: ignore[import-untyped]
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.channels.whatsapp.client import WhatsAppRetryableError, get_whatsapp_client
from app.config import settings
from app.db.models import Announcement, AnnouncementDelivery
from app.db.session import SessionLocal
from app.modules.announcements.service import AnnouncementService
from app.utils.logger import logger

MAX_ATTEMPTS = int(getattr(settings, "ANNOUNCEMENT_RETRY_MAX", 3))
BACKOFF_SECONDS = int(getattr(settings, "ANNOUNCEMENT_RETRY_BASE_SECONDS", 2))
JOB_TIMEOUT_SECONDS = int(getattr(settings, "ANNOUNCEMENT_JOB_TIMEOUT_SECONDS", 120))


def _redis_connection():
    import redis

    return redis.from_url(str(getattr(settings, "REDIS_URL", "redis://localhost:6379/0")))


def _queue_for_channel(channel: str):
    from rq import Queue

    queue_name = str(getattr(settings, "ANNOUNCEMENT_QUEUE_DEFAULT", "announcement-default"))
    if channel == "whatsapp":
        queue_name = str(getattr(settings, "ANNOUNCEMENT_QUEUE_WHATSAPP", "announcement-whatsapp"))
    return Queue(queue_name, connection=_redis_connection(), default_timeout=JOB_TIMEOUT_SECONDS)


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, WhatsAppRetryableError):
        return True
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


def _get_whatsapp_policy_state(delivery: AnnouncementDelivery) -> dict:
    metadata = dict((delivery.member_identity.metadata_json or {})) if delivery.member_identity else {}
    channel_state = dict(metadata.get("channel_state") or {})
    return dict(channel_state.get("whatsapp") or {})


def _resolve_policy_outcome(delivery: AnnouncementDelivery) -> tuple[str, str | None]:
    state = _get_whatsapp_policy_state(delivery)
    if not state.get("opt_in"):
        return "skipped_no_opt_in", "Recipient has no opt-in state for WhatsApp announcements"
    if not delivery.rendered_payload:
        return "failed_template_required", "Announcement rendered payload is missing"

    payload: dict[str, Any] = cast(dict[str, Any], delivery.rendered_payload) if isinstance(delivery.rendered_payload, dict) else {}
    template_name = str(payload.get("template_name") or "").strip()
    if not template_name:
        return "failed_template_required", "Announcement template is not configured"

    return "sent_template", None


def _send_delivery(delivery: AnnouncementDelivery) -> tuple[str, str | None]:
    if delivery.status == "sent":
        return "sent_template", None
    if delivery.channel != "whatsapp":
        raise ValueError(f"Unsupported channel: {delivery.channel}")
    if not delivery.announcement or not delivery.announcement.message_text:
        raise ValueError("Announcement payload is missing message text")

    policy_outcome, reason = _resolve_policy_outcome(delivery)
    if policy_outcome in {"skipped_no_opt_in", "failed_template_required"}:
        return policy_outcome, reason

    AnnouncementService.ensure_whatsapp_template_delivery(
        channel=str(delivery.channel),
        uses_template_path=policy_outcome == "sent_template",
    )

    payload: dict[str, Any] = cast(dict[str, Any], delivery.rendered_payload) if isinstance(delivery.rendered_payload, dict) else {}
    template_name = str(payload.get("template_name"))
    body_parameters = list(payload.get("body_parameters") or [])
    if not body_parameters or any(not str(param).strip() for param in body_parameters):
        raise ValueError("Announcement payload has empty template placeholders")

    client = get_whatsapp_client()
    client.send_template_message(
        to_phone=str(delivery.recipient_id),
        template_name=template_name,
        body_parameters=body_parameters,
    )
    return "sent_template", None


def _refresh_announcement_summary(db, *, announcement_id) -> dict[str, int]:
    status_counts = {
        status: count
        for status, count in (
            db.query(AnnouncementDelivery.status, func.count())
            .filter(AnnouncementDelivery.announcement_id == announcement_id)
            .group_by(AnnouncementDelivery.status)
            .all()
        )
    }
    sent_count = int(status_counts.get("sent", 0))
    failed_count = int(status_counts.get("failed", 0))
    skipped_count = int(status_counts.get("skipped", 0))
    total_targets = int(sum(int(value) for value in status_counts.values()))

    db.query(Announcement).filter(Announcement.id == announcement_id).update(
        {
            Announcement.total_targets: total_targets,
            Announcement.sent_count: sent_count,
            Announcement.failed_count: failed_count,
            Announcement.skipped_count: skipped_count,
        },
        synchronize_session=False,
    )

    return {
        "total_targets": total_targets,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
    }


def enqueue_announcement_delivery_tasks(*, announcement_id: str) -> int:
    db = SessionLocal()
    enqueued = 0
    try:
        deliveries = (
            db.query(AnnouncementDelivery)
            .filter(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.sent_at.is_(None),
                AnnouncementDelivery.status.in_(["pending", "processing"]),
            )
            .all()
        )
        for delivery in deliveries:
            enqueued += enqueue_delivery_by_key(
                announcement_id=str(delivery.announcement_id),
                member_identity_id=str(delivery.member_identity_id),
                channel=str(delivery.channel),
            )
        logger.info("Announcement delivery enqueue complete", extra={"announcement_id": announcement_id, "enqueued": enqueued})
        return enqueued
    finally:
        db.close()


def enqueue_delivery_by_key(*, announcement_id: str, member_identity_id: str, channel: str) -> int:
    queue = _queue_for_channel(channel)
    job_id = f"announcement-delivery:{announcement_id}:{member_identity_id}:{channel}"
    from rq.job import Retry

    retry = Retry(max=MAX_ATTEMPTS - 1, interval=[BACKOFF_SECONDS * (2**i) for i in range(max(MAX_ATTEMPTS - 1, 1))])
    try:
        queue.enqueue(
            process_announcement_delivery,
            announcement_id,
            member_identity_id,
            channel,
            job_id=job_id,
            retry=retry,
            result_ttl=300,
            failure_ttl=3600,
        )
        return 1
    except Exception:
        logger.info("Announcement delivery already enqueued", extra={"job_id": job_id})
        return 0


def process_announcement_delivery(announcement_id: str, member_identity_id: str, channel: str) -> str:
    db = SessionLocal()
    try:
        delivery = (
            db.query(AnnouncementDelivery)
            .options(joinedload(AnnouncementDelivery.announcement), joinedload(AnnouncementDelivery.member_identity))
            .filter(
                AnnouncementDelivery.announcement_id == announcement_id,
                AnnouncementDelivery.member_identity_id == member_identity_id,
                AnnouncementDelivery.channel == channel,
            )
            .one_or_none()
        )
        if delivery is None:
            return "missing"
        if delivery.sent_at is not None or delivery.status == "sent":
            return "already_sent"

        delivery.status = "processing"
        delivery.processing_started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            policy_outcome, reason = _send_delivery(delivery)
            delivery.attempts += 1
            delivery.processing_started_at = None

            if policy_outcome.startswith("sent_"):
                delivery.status = "sent"
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.last_error = None
            elif policy_outcome.startswith("skipped_"):
                delivery.status = "skipped"
                delivery.last_error = reason
            else:
                delivery.status = "failed"
                delivery.last_error = reason

            summary = _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
            db.commit()
            logger.info("Announcement delivery processed", extra={"announcement_id": str(delivery.announcement_id), "member_identity_id": str(delivery.member_identity_id), "channel": delivery.channel, "policy_outcome": policy_outcome, "outcomes": summary})
            return policy_outcome
        except Exception as exc:
            delivery.attempts += 1
            delivery.processing_started_at = None
            delivery.last_error = str(exc)[:2000]
            db.commit()
            if _is_transient_error(exc) and delivery.attempts < MAX_ATTEMPTS:
                delivery.status = "pending"
                db.commit()
                logger.warning("Announcement delivery transient error; retry delegated to queue", extra={"announcement_id": str(delivery.announcement_id), "member_identity_id": str(delivery.member_identity_id), "attempts": delivery.attempts})
                raise

            delivery.status = "failed"
            summary = _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
            db.commit()
            logger.exception("Announcement delivery failed", extra={"announcement_id": str(delivery.announcement_id), "member_identity_id": str(delivery.member_identity_id), "channel": delivery.channel, "attempts": delivery.attempts, "outcomes": summary})
            raise
    finally:
        db.close()


def run_pending_announcement_deliveries(*, batch_size: int = 20, **_kwargs) -> int:
    db = SessionLocal()
    try:
        pending = (
            db.query(AnnouncementDelivery)
            .filter(AnnouncementDelivery.sent_at.is_(None), AnnouncementDelivery.status.in_(["pending", "processing"]))
            .limit(batch_size)
            .all()
        )
        enqueued = 0
        for delivery in pending:
            enqueued += enqueue_delivery_by_key(
                announcement_id=str(delivery.announcement_id),
                member_identity_id=str(delivery.member_identity_id),
                channel=str(delivery.channel),
            )
        return enqueued
    finally:
        db.close()
