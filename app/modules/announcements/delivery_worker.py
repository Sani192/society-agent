#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Announcement delivery worker supporting local and RQ-backed dispatch."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import time
import requests  # type: ignore[import-untyped]
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, text
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
BATCH_SIZE = int(getattr(settings, "ANNOUNCEMENT_BATCH_SIZE", 20))
SCHEDULER_INTERVAL_SECONDS = int(getattr(settings, "ANNOUNCEMENT_SCHEDULER_INTERVAL_SECONDS", 30))
DISPATCH_BACKEND = str(getattr(settings, "ANNOUNCEMENT_DISPATCH_BACKEND", "local")).strip().lower()

announcement_delivery_scheduler = BackgroundScheduler()


def _rq_enabled() -> bool:
    if DISPATCH_BACKEND != "rq":
        return False
    try:
        import redis  # noqa: F401
        import rq  # noqa: F401
        return True
    except Exception:
        logger.warning("ANNOUNCEMENT_DISPATCH_BACKEND=rq but rq/redis not installed; falling back to local backend")
        return False


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
        return enqueued
    finally:
        db.close()


def enqueue_delivery_by_key(*, announcement_id: str, member_identity_id: str, channel: str) -> int:
    if not _rq_enabled():
        return 0

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

            if _is_transient_error(exc) and delivery.attempts < MAX_ATTEMPTS:
                delivery.status = "pending"
                db.commit()
                logger.warning("Announcement delivery transient error; retry deferred", extra={"announcement_id": str(delivery.announcement_id), "member_identity_id": str(delivery.member_identity_id), "attempts": delivery.attempts})
                if _rq_enabled():
                    raise
                return "retry_deferred"

            delivery.status = "failed"
            summary = _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
            db.commit()
            logger.exception("Announcement delivery failed", extra={"announcement_id": str(delivery.announcement_id), "member_identity_id": str(delivery.member_identity_id), "channel": delivery.channel, "attempts": delivery.attempts, "outcomes": summary})
            if _rq_enabled():
                raise
            return "failed"
    finally:
        db.close()


def _process_delivery_instance(delivery, *, db, send_interval_seconds: float = 0.0) -> str:
    if delivery.sent_at is not None or delivery.status == "sent":
        return "already_sent"

    try:
        policy_outcome, reason = _send_delivery(delivery)
        delivery.attempts += 1
        delivery.processing_started_at = None

        if policy_outcome.startswith("sent_"):
            delivery.status = "sent"
            delivery.sent_at = datetime.now(timezone.utc)
            delivery.last_error = None
            if send_interval_seconds > 0:
                time.sleep(send_interval_seconds)
        elif policy_outcome.startswith("skipped_"):
            delivery.status = "skipped"
            delivery.last_error = reason
        else:
            delivery.status = "failed"
            delivery.last_error = reason

        _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
        db.commit()
        return policy_outcome
    except Exception as exc:
        delivery.attempts += 1
        delivery.processing_started_at = None
        delivery.last_error = str(exc)[:2000]

        if _is_transient_error(exc) and delivery.attempts < MAX_ATTEMPTS:
            delivery.status = "pending"
            db.commit()
            retry_after_seconds = exc.retry_after_seconds if isinstance(exc, WhatsAppRetryableError) else None
            sleep_for = retry_after_seconds if retry_after_seconds is not None else BACKOFF_SECONDS * (2 ** (delivery.attempts - 1))
            time.sleep(max(float(sleep_for), 0.0))
            if _rq_enabled():
                raise
            return "retry_deferred"

        delivery.status = "failed"
        _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
        db.commit()
        if _rq_enabled():
            raise
        return "failed"


def _claim_pending_deliveries(db, *, batch_size: int) -> list[tuple[str, str, str]]:
    rows = db.execute(
        text(
            """
            WITH candidates AS (
                SELECT announcement_id, member_identity_id, channel
                FROM announcement_deliveries
                WHERE sent_at IS NULL
                  AND status IN ('pending', 'processing')
                ORDER BY announcement_id, member_identity_id
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            UPDATE announcement_deliveries ad
            SET status = 'processing', processing_started_at = :now
            FROM candidates
            WHERE ad.announcement_id = candidates.announcement_id
              AND ad.member_identity_id = candidates.member_identity_id
              AND ad.channel = candidates.channel
            RETURNING ad.announcement_id, ad.member_identity_id, ad.channel
            """
        ),
        {"batch_size": batch_size, "now": datetime.now(timezone.utc)},
    ).fetchall()
    db.commit()
    return [(str(row.announcement_id), str(row.member_identity_id), str(row.channel)) for row in rows]


def run_pending_announcement_deliveries(
    *,
    batch_size: int = BATCH_SIZE,
    send_interval_seconds: float = 0.0,
    **_kwargs,
) -> int:
    db = SessionLocal()
    try:
        claimed = _claim_pending_deliveries(db, batch_size=batch_size)

        processed = 0
        for item in claimed:
            if isinstance(item, tuple) and len(item) == 3:
                announcement_id, member_identity_id, channel = item
                if _rq_enabled():
                    processed += enqueue_delivery_by_key(
                        announcement_id=str(announcement_id),
                        member_identity_id=str(member_identity_id),
                        channel=str(channel),
                    )
                else:
                    outcome = process_announcement_delivery(str(announcement_id), str(member_identity_id), str(channel))
                    if outcome.startswith("sent_"):
                        processed += 1
                continue

            delivery = item
            if _rq_enabled():
                processed += enqueue_delivery_by_key(
                    announcement_id=str(delivery.announcement_id),
                    member_identity_id=str(delivery.member_identity_id),
                    channel=str(delivery.channel),
                )
                continue

            outcome = _process_delivery_instance(delivery, db=db, send_interval_seconds=send_interval_seconds)
            if outcome.startswith("sent_"):
                processed += 1

        return processed
    finally:
        db.close()


def start_announcement_delivery_scheduler() -> None:
    announcement_delivery_scheduler.add_job(
        run_pending_announcement_deliveries,
        trigger="interval",
        seconds=SCHEDULER_INTERVAL_SECONDS,
        id="announcement_delivery_dispatch",
        replace_existing=True,
    )
    announcement_delivery_scheduler.start()


def acquire_announcement_scheduler_leader_lock(lock_key: int = 937452):
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": lock_key})
        if bool(result.scalar()):
            return db
        db.close()
        return None
    except Exception:
        logger.exception("Failed to acquire announcement scheduler advisory lock")
        db.close()
        return None
