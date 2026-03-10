#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Background delivery worker for queued announcements."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, cast

import requests  # type: ignore[import-untyped]
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, text, tuple_
from sqlalchemy.orm import joinedload

from app.channels.whatsapp.client import WhatsAppRetryableError, get_whatsapp_client
from app.config import settings
from app.db.models import Announcement, AnnouncementDelivery
from app.modules.announcements.service import AnnouncementService
from app.db.session import SessionLocal
from app.utils.logger import logger

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2
SEND_INTERVAL_SECONDS = 0.25
BATCH_SIZE = 20
SCHEDULER_INTERVAL_SECONDS = 30

MAX_SENDS_PER_BATCH = int(getattr(settings, "ANNOUNCEMENT_MAX_SENDS_PER_BATCH", "100"))
MAX_SENDS_PER_MINUTE = int(getattr(settings, "ANNOUNCEMENT_MAX_SENDS_PER_MINUTE", "60"))
ERROR_RATE_THRESHOLD = float(getattr(settings, "ANNOUNCEMENT_ERROR_RATE_THRESHOLD", "0.4"))
CIRCUIT_BREAKER_MIN_ATTEMPTS = int(getattr(settings, "ANNOUNCEMENT_CIRCUIT_BREAKER_MIN_ATTEMPTS", "10"))
PROCESSING_TIMEOUT_SECONDS = int(getattr(settings, "ANNOUNCEMENT_PROCESSING_TIMEOUT_SECONDS", "300"))

announcement_delivery_scheduler = BackgroundScheduler()


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

    payload: dict[str, Any] = (
        cast(dict[str, Any], delivery.rendered_payload) if isinstance(delivery.rendered_payload, dict) else {}
    )
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

    payload: dict[str, Any] = (
        cast(dict[str, Any], delivery.rendered_payload) if isinstance(delivery.rendered_payload, dict) else {}
    )
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


def _claim_pending_deliveries(db, *, batch_size: int) -> list[AnnouncementDelivery]:
    now = datetime.now(timezone.utc)
    stuck_before = datetime.fromtimestamp(now.timestamp() - PROCESSING_TIMEOUT_SECONDS, tz=timezone.utc)

    claimed_rows = db.execute(
        text(
            """
            WITH candidates AS (
                SELECT announcement_id, member_identity_id, channel
                FROM announcement_deliveries
                WHERE sent_at IS NULL
                  AND (
                    status = 'pending'
                    OR (status = 'processing' AND processing_started_at < :stuck_before)
                  )
                ORDER BY announcement_id
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            UPDATE announcement_deliveries AS ad
            SET status = 'processing',
                processing_started_at = :now
            FROM candidates
            WHERE ad.announcement_id = candidates.announcement_id
              AND ad.member_identity_id = candidates.member_identity_id
              AND ad.channel = candidates.channel
            RETURNING ad.announcement_id, ad.member_identity_id, ad.channel
            """
        ),
        {"batch_size": batch_size, "now": now, "stuck_before": stuck_before},
    ).fetchall()
    db.commit()

    if not claimed_rows:
        return []

    claimed_keys = [
        {
            "announcement_id": row.announcement_id,
            "member_identity_id": row.member_identity_id,
            "channel": row.channel,
        }
        for row in claimed_rows
    ]

    return (
        db.query(AnnouncementDelivery)
        .options(
            joinedload(AnnouncementDelivery.announcement),
            joinedload(AnnouncementDelivery.member_identity),
        )
        .filter(
            tuple_(
                AnnouncementDelivery.announcement_id,
                AnnouncementDelivery.member_identity_id,
                AnnouncementDelivery.channel,
            ).in_(
                [
                    (
                        row["announcement_id"],
                        row["member_identity_id"],
                        row["channel"],
                    )
                    for row in claimed_keys
                ]
            )
        )
        .all()
    )


def run_pending_announcement_deliveries(
    *,
    batch_size: int = BATCH_SIZE,
    send_interval_seconds: float = SEND_INTERVAL_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
    backoff_seconds: float = BACKOFF_SECONDS,
) -> int:
    db = SessionLocal()
    processed_count = 0
    attempt_count = 0
    error_count = 0
    minute_window_start = time.monotonic()
    sent_in_current_minute = 0
    per_announcement_outcomes: dict[str, dict[str, int]] = {}

    try:
        pending_deliveries = _claim_pending_deliveries(db, batch_size=batch_size)

        for delivery in pending_deliveries:
            if processed_count >= MAX_SENDS_PER_BATCH:
                logger.warning(
                    "Announcement batch send cap reached",
                    extra={"max_sends_per_batch": MAX_SENDS_PER_BATCH, "batch_size": batch_size},
                )
                break

            if delivery.status != "processing" or delivery.sent_at is not None:
                continue

            if sent_in_current_minute >= MAX_SENDS_PER_MINUTE:
                elapsed = time.monotonic() - minute_window_start
                if elapsed < 60:
                    time.sleep(60 - elapsed)
                minute_window_start = time.monotonic()
                sent_in_current_minute = 0

            try:
                attempt_count += 1
                policy_outcome, reason = _send_delivery(delivery)

                delivery.attempts += 1
                delivery.processing_started_at = None
                announcement_key = str(delivery.announcement_id)
                per_announcement_outcomes.setdefault(
                    announcement_key,
                    {"sent": 0, "failed": 0, "skipped": 0},
                )
                if policy_outcome.startswith("sent_"):
                    delivery.status = "sent"
                    delivery.last_error = None
                    delivery.sent_at = datetime.now(timezone.utc)
                    processed_count += 1
                    sent_in_current_minute += 1
                    per_announcement_outcomes[announcement_key]["sent"] += 1
                    time.sleep(send_interval_seconds)
                elif policy_outcome.startswith("skipped_"):
                    delivery.status = "skipped"
                    delivery.last_error = reason
                    per_announcement_outcomes[announcement_key]["skipped"] += 1
                else:
                    delivery.status = "failed"
                    delivery.last_error = reason
                    per_announcement_outcomes[announcement_key]["failed"] += 1

                summary = _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
                db.commit()
                logger.info(
                    "Announcement delivery policy outcome",
                    extra={
                        "announcement_id": str(delivery.announcement_id),
                        "society_id": str(getattr(delivery.announcement, "society_id", "")),
                        "event_id": str(getattr(delivery.announcement, "event_id", "")) if getattr(delivery.announcement, "event_id", None) else None,
                        "member_identity_id": str(delivery.member_identity_id),
                        "channel": delivery.channel,
                        "batch_size": batch_size,
                        "policy_outcome": policy_outcome,
                        "reason": reason,
                        "outcomes": summary,
                    },
                )
            except Exception as exc:  # intentionally broad for delivery safety
                error_count += 1
                delivery.attempts += 1
                is_transient = _is_transient_error(exc)
                delivery.last_error = str(exc)[:2000]
                delivery.processing_started_at = None

                if attempt_count >= CIRCUIT_BREAKER_MIN_ATTEMPTS:
                    error_rate = error_count / attempt_count if attempt_count else 0.0
                    if error_rate >= ERROR_RATE_THRESHOLD:
                        logger.error(
                            "Announcement delivery circuit breaker opened",
                            extra={
                                "attempt_count": attempt_count,
                                "error_count": error_count,
                                "error_rate": error_rate,
                                "threshold": ERROR_RATE_THRESHOLD,
                            },
                        )
                        db.commit()
                        return processed_count

                if is_transient and delivery.attempts < max_attempts:
                    delivery.status = "pending"
                    db.commit()
                    retry_after_seconds = None
                    if isinstance(exc, WhatsAppRetryableError):
                        retry_after_seconds = exc.retry_after_seconds
                    sleep_for = retry_after_seconds if retry_after_seconds is not None else backoff_seconds * (2 ** (delivery.attempts - 1))
                    logger.warning(
                        "Announcement delivery retry scheduled",
                        extra={
                            "announcement_id": str(delivery.announcement_id),
                            "society_id": str(getattr(delivery.announcement, "society_id", "")),
                            "event_id": str(getattr(delivery.announcement, "event_id", "")) if getattr(delivery.announcement, "event_id", None) else None,
                            "batch_size": batch_size,
                            "attempts": delivery.attempts,
                            "sleep_for_seconds": max(sleep_for, 0),
                            "outcomes": per_announcement_outcomes.get(str(delivery.announcement_id), {"sent": 0, "failed": 0, "skipped": 0}),
                        },
                    )
                    time.sleep(max(sleep_for, 0))
                    continue

                delivery.status = "failed"
                announcement_key = str(delivery.announcement_id)
                per_announcement_outcomes.setdefault(announcement_key, {"sent": 0, "failed": 0, "skipped": 0})
                per_announcement_outcomes[announcement_key]["failed"] += 1
                summary = _refresh_announcement_summary(db, announcement_id=delivery.announcement_id)
                db.commit()
                logger.exception(
                    "Announcement delivery failed",
                    extra={
                        "announcement_id": str(delivery.announcement_id),
                        "society_id": str(getattr(delivery.announcement, "society_id", "")),
                        "event_id": str(getattr(delivery.announcement, "event_id", "")) if getattr(delivery.announcement, "event_id", None) else None,
                        "member_identity_id": str(delivery.member_identity_id),
                        "channel": delivery.channel,
                        "attempts": delivery.attempts,
                        "batch_size": batch_size,
                        "outcomes": summary,
                    },
                )

        logger.info(
            "Announcement dispatch batch completed",
            extra={
                "batch_size": batch_size,
                "processed_count": processed_count,
                "outcomes": per_announcement_outcomes,
            },
        )
        return processed_count
    except Exception:
        logger.exception("Error running announcement delivery dispatch batch")
        return processed_count
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
    logger.info(
        "Announcement delivery scheduler loaded at %s-second interval",
        SCHEDULER_INTERVAL_SECONDS,
    )


def acquire_announcement_scheduler_leader_lock(lock_key: int = 937452):
    """Acquire and hold a session-scoped PostgreSQL advisory lock."""
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
