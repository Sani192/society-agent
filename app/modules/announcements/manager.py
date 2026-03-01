#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Application-level orchestration for committee announcements."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import cast

from sqlalchemy.orm import Session

from app.db.models import Event
from app.modules.announcements.delivery_worker import run_pending_announcement_deliveries
from app.modules.announcements.recipient_service import AnnouncementRecipientService
from app.modules.announcements.service import AnnouncementRecipient, AnnouncementService
from app.utils.logger import logger


@dataclass(frozen=True)
class QueueAnnouncementResult:
    announcement_id: str
    accepted_count: int
    skipped_count: int


class AnnouncementManager:
    @staticmethod
    def resolve_current_event(*, db: Session, society_id):
        return (
            db.query(Event)
            .filter(
                Event.society_id == society_id,
                Event.status.in_(["ACTIVE", "LOCKED", "EVENT_DAY"]),
            )
            .order_by(Event.event_date.desc())
            .first()
        )

    @staticmethod
    def trigger_delivery_async() -> None:
        thread = threading.Thread(
            target=run_pending_announcement_deliveries,
            kwargs={"batch_size": 20},
            daemon=True,
        )
        thread.start()

    @staticmethod
    def queue(
        *,
        db: Session,
        member,
        event,
        message_body: str,
        scope: str,
    ) -> QueueAnnouncementResult:
        if scope == "event":
            target_event = event or AnnouncementManager.resolve_current_event(
                db=db,
                society_id=member.society_id,
            )
            if not target_event:
                raise ValueError("No active event found. Please contact committee.")
            recipient_resolution = AnnouncementRecipientService.get_event_joined_member_targets(
                db=db,
                society_id=member.society_id,
                event_id=target_event.id,
            )
            announcement_type = "event"
        else:
            target_event = None
            recipient_resolution = AnnouncementRecipientService.get_active_member_targets(
                db=db,
                society_id=member.society_id,
            )
            announcement_type = "announcement"

        announcement = AnnouncementService.create_announcement(
            db,
            society_id=member.society_id,
            event_id=getattr(target_event, "id", None),
            announcement_type=announcement_type,
            message_text=message_body,
            created_by=member.id,
            recipients=cast(list[AnnouncementRecipient], recipient_resolution["targets"]),
        )

        AnnouncementManager.trigger_delivery_async()

        accepted_count = recipient_resolution["queued_count"]
        skipped_count = recipient_resolution["total_candidates"] - accepted_count
        logger.info(
            "Queued WhatsApp announcement",
            extra={
                "scope": scope,
                "society_id": str(member.society_id),
                "accepted_count": accepted_count,
                "skipped_count": skipped_count,
                "announcement_id": str(announcement.id),
                "initiated_by": str(getattr(member, "id", "unknown")),
                "message_preview": message_body[:120],
            },
        )
        return QueueAnnouncementResult(
            announcement_id=str(announcement.id),
            accepted_count=accepted_count,
            skipped_count=skipped_count,
        )
