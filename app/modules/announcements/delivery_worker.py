#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Background delivery worker for queued announcements."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import joinedload

from app.channels.whatsapp.client import get_whatsapp_client
from app.db.models import AnnouncementDelivery
from app.db.session import SessionLocal
from app.utils.logger import logger

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2
SEND_INTERVAL_SECONDS = 0.25
BATCH_SIZE = 20
SCHEDULER_INTERVAL_SECONDS = 30

announcement_delivery_scheduler = BackgroundScheduler()


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True

    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in {429, 500, 502, 503, 504}

    return False


def _send_delivery(delivery: AnnouncementDelivery) -> None:
    if delivery.status == "sent":
        return

    if delivery.channel != "whatsapp":
        raise ValueError(f"Unsupported channel: {delivery.channel}")

    if not delivery.announcement or not delivery.announcement.message_text:
        raise ValueError("Announcement payload is missing message text")

    client = get_whatsapp_client()
    client.send_text_message(delivery.recipient_id, delivery.announcement.message_text)


def run_pending_announcement_deliveries(
    *,
    batch_size: int = BATCH_SIZE,
    send_interval_seconds: float = SEND_INTERVAL_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
    backoff_seconds: float = BACKOFF_SECONDS,
) -> int:
    db = SessionLocal()
    processed_count = 0

    try:
        pending_deliveries = (
            db.query(AnnouncementDelivery)
            .options(joinedload(AnnouncementDelivery.announcement))
            .filter(AnnouncementDelivery.status == "pending")
            .filter(AnnouncementDelivery.sent_at.is_(None))
            .order_by(AnnouncementDelivery.announcement_id)
            .limit(batch_size)
            .all()
        )

        for delivery in pending_deliveries:
            # Idempotency guard.
            if delivery.status == "sent" or delivery.sent_at is not None:
                continue

            while delivery.attempts < max_attempts and delivery.status != "sent":
                try:
                    _send_delivery(delivery)
                    delivery.attempts += 1
                    delivery.status = "sent"
                    delivery.last_error = None
                    delivery.sent_at = datetime.now(timezone.utc)
                    db.commit()
                    processed_count += 1
                    time.sleep(send_interval_seconds)
                except Exception as exc:  # intentionally broad for delivery safety
                    delivery.attempts += 1
                    is_transient = _is_transient_error(exc)
                    delivery.last_error = str(exc)[:2000]

                    if is_transient and delivery.attempts < max_attempts:
                        delivery.status = "pending"
                        db.commit()
                        time.sleep(backoff_seconds * (2 ** (delivery.attempts - 1)))
                        continue

                    delivery.status = "failed"
                    db.commit()
                    logger.exception(
                        "Announcement delivery failed",
                        extra={
                            "announcement_id": str(delivery.announcement_id),
                            "member_identity_id": str(delivery.member_identity_id),
                            "channel": delivery.channel,
                            "attempts": delivery.attempts,
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
