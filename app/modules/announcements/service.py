#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Announcement creation service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Announcement, AnnouncementDelivery


class AnnouncementService:
    MAX_FREE_TEXT_LENGTH = 1024
    GENERAL_TEMPLATE_NAME = "society_announcement_general"
    EVENT_TEMPLATE_NAME = "society_announcement_event"

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
    def build_whatsapp_template_payload(
        *,
        announcement_type: str,
        receiver_name: str,
        free_text: str,
        event_name: str | None,
    ) -> dict:
        """Resolve WhatsApp template metadata and ordered body variables."""

        receiver_name_clean = (receiver_name or "").strip()
        free_text_clean = (free_text or "").strip()
        event_name_clean = (event_name or "").strip()

        if not receiver_name_clean:
            raise ValueError("receiver_name is required")
        if not free_text_clean:
            raise ValueError("free_text is required")
        if len(free_text_clean) > AnnouncementService.MAX_FREE_TEXT_LENGTH:
            raise ValueError(
                f"free_text exceeds max length of {AnnouncementService.MAX_FREE_TEXT_LENGTH} characters"
            )

        is_event_related = bool(event_name_clean) or str(announcement_type).strip().lower() in {
            "event",
            "event_related",
            "event-related",
            "event_announcement",
        }

        if is_event_related and not event_name_clean:
            raise ValueError("event_name is required for event-related announcements")

        if is_event_related:
            return {
                "template_name": AnnouncementService.EVENT_TEMPLATE_NAME,
                "body_parameters": [receiver_name_clean, event_name_clean, free_text_clean],
            }

        return {
            "template_name": AnnouncementService.GENERAL_TEMPLATE_NAME,
            "body_parameters": [receiver_name_clean, free_text_clean],
        }

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
                "recipient_id": "<external channel user id>",
                "receiver_name": "<recipient display name>",
                "event_name": "<event name>",
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

            channel = recipient.get("channel", "whatsapp")
            rendered_payload = None
            if channel == "whatsapp":
                rendered_payload = AnnouncementService.build_whatsapp_template_payload(
                    announcement_type=announcement_type,
                    receiver_name=str(recipient.get("receiver_name") or ""),
                    free_text=message_text,
                    event_name=recipient.get("event_name") or recipient.get("announcement_event_name"),
                )

            db.add(
                AnnouncementDelivery(
                    announcement_id=announcement.id,
                    member_identity_id=recipient["member_identity_id"],
                    channel=channel,
                    recipient_id=recipient_id,
                    rendered_payload=rendered_payload,
                    status="pending",
                    attempts=0,
                )
            )

        db.commit()
        db.refresh(announcement)
        return announcement
