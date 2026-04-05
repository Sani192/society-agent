#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Announcement creation and template rendering service."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Announcement, AnnouncementDelivery
from app.modules.users.language_service import DEFAULT_LANGUAGE, normalize_language_code
from app.utils.audit_logger import log_announcement_creation


class AnnouncementRecipient(TypedDict, total=False):
    member_identity_id: UUID
    channel: str
    receiver_name: str
    event_name: str
    preferred_language: str


class RenderedTemplatePayload(TypedDict):
    template_name: str
    body_parameters: list[str]
    app_language_code: str
    template_locale_code: str


class AnnouncementService:
    MAX_FREE_TEXT_LENGTH = 1024
    GENERAL_TEMPLATE_NAME = "society_announcement_general"
    EVENT_TEMPLATE_NAME = "society_announcement_event"
    TEMPLATE_LOCALE_BY_APP_LANGUAGE = {
        "en": "en_US",
        "hi": "hi_IN",
        "gu": "gu_IN",
    }

    @staticmethod
    def ensure_whatsapp_template_delivery(*, channel: str, uses_template_path: bool) -> None:
        """Enforce template-only delivery for WhatsApp announcement dispatches."""

        if channel == "whatsapp" and not uses_template_path:
            raise ValueError("WhatsApp announcement deliveries must use template messaging")

    @staticmethod
    def _is_event_related(*, announcement_type: str, event_name: str) -> bool:
        return bool(event_name) or str(announcement_type).strip().lower() in {
            "event",
            "event_related",
            "event-related",
            "event_announcement",
        }

    @staticmethod
    def build_whatsapp_template_payload(
        *,
        announcement_type: str,
        receiver_name: str,
        free_text: str,
        event_name: str | None,
        app_language_code: str | None = None,
    ) -> RenderedTemplatePayload:
        """Resolve WhatsApp template metadata and ordered body variables."""

        receiver_name_clean = (receiver_name or "").strip()
        free_text_clean = (free_text or "").strip()
        event_name_clean = (event_name or "").strip()

        normalized_app_language = normalize_language_code(app_language_code) or DEFAULT_LANGUAGE
        template_locale_code = AnnouncementService.TEMPLATE_LOCALE_BY_APP_LANGUAGE.get(
            normalized_app_language,
            AnnouncementService.TEMPLATE_LOCALE_BY_APP_LANGUAGE[DEFAULT_LANGUAGE],
        )

        if not receiver_name_clean:
            raise ValueError("receiver_name is required")
        if not free_text_clean:
            raise ValueError("free_text is required")
        if len(free_text_clean) > AnnouncementService.MAX_FREE_TEXT_LENGTH:
            raise ValueError(
                f"free_text exceeds max length of {AnnouncementService.MAX_FREE_TEXT_LENGTH} characters"
            )

        if AnnouncementService._is_event_related(
            announcement_type=announcement_type,
            event_name=event_name_clean,
        ):
            if not event_name_clean:
                raise ValueError("event_name is required for event-related announcements")
            return {
                "template_name": AnnouncementService.EVENT_TEMPLATE_NAME,
                "body_parameters": [receiver_name_clean, event_name_clean, free_text_clean],
                "app_language_code": normalized_app_language,
                "template_locale_code": template_locale_code,
            }

        return {
            "template_name": AnnouncementService.GENERAL_TEMPLATE_NAME,
            "body_parameters": [receiver_name_clean, free_text_clean],
            "app_language_code": normalized_app_language,
            "template_locale_code": template_locale_code,
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
        recipients: list[AnnouncementRecipient],
    ) -> Announcement:
        """Create an announcement and pending delivery rows."""

        queued_recipients = [
            recipient
            for recipient in recipients
            if recipient.get("member_identity_id")
        ]

        announcement = Announcement(
            society_id=society_id,
            event_id=event_id,
            type=announcement_type,
            message_text=message_text,
            created_by=created_by,
            status="queued",
            total_targets=len(queued_recipients),
            sent_count=0,
            failed_count=0,
            skipped_count=0,
        )
        db.add(announcement)
        db.flush()

        for recipient in queued_recipients:
            channel = str(recipient.get("channel", "whatsapp"))
            rendered_payload: RenderedTemplatePayload | None = None
            if channel == "whatsapp":
                rendered_payload = AnnouncementService.build_whatsapp_template_payload(
                    announcement_type=announcement_type,
                    receiver_name=str(recipient.get("receiver_name") or ""),
                    free_text=message_text,
                    event_name=recipient.get("event_name"),
                    app_language_code=str(recipient.get("preferred_language") or ""),
                )

            db.add(
                AnnouncementDelivery(
                    announcement_id=announcement.id,
                    member_identity_id=recipient["member_identity_id"],
                    channel=channel,
                    rendered_payload=rendered_payload,
                    status="pending",
                    attempts=0,
                )
            )

        log_announcement_creation(
            db,
            society_id=society_id,
            announcement_id=announcement.id,
            announcement_type=announcement_type,
            message_text=message_text,
            performed_by=created_by,
        )
        db.commit()
        db.refresh(announcement)
        return announcement
