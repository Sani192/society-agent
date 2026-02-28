#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Announcement creation service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Announcement, AnnouncementDelivery


class AnnouncementService:

    @staticmethod
    def guard_whatsapp_announcement_delivery(
        *,
        channel: str,
        announcement_type: str,
        uses_template_path: bool,
    ) -> None:
        """Enforce template-only delivery for WhatsApp announcement dispatches."""

        if channel == "whatsapp" and announcement_type == "announcement" and not uses_template_path:
            raise ValueError("WhatsApp announcement deliveries must use template messaging")

    @staticmethod
    def create_announcement(
        db: Session,
        *,
        society_id: UUID,
        event_id: UUID | None,
        announcement_type: str,
        message_text: str,
        created_by: UUID,
        recipients: list[dict],
    ) -> Announcement:
        """
        Create an announcement and pending delivery rows.

        recipients item schema:
            {
                "member_identity_id": "<uuid>",
                "channel": "whatsapp",  # optional, defaults to whatsapp
                "recipient_id": "<external channel user id>"
            }
        """

        announcement = Announcement(
            society_id=society_id,
            event_id=event_id,
            type=announcement_type,
            message_text=message_text,
            created_by=created_by,
            status="queued",
        )
        db.add(announcement)
        db.flush()

        for recipient in recipients:
            recipient_id = recipient.get("recipient_id") or recipient.get("whatsapp_user_id")
            if not recipient_id:
                continue

            db.add(
                AnnouncementDelivery(
                    announcement_id=announcement.id,
                    member_identity_id=recipient["member_identity_id"],
                    channel=recipient.get("channel", "whatsapp"),
                    recipient_id=recipient_id,
                    status="pending",
                    attempts=0,
                )
            )

        db.commit()
        db.refresh(announcement)
        return announcement
