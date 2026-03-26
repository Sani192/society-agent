#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Recipient targeting helpers for WhatsApp announcements."""

from __future__ import annotations

from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Event, Flat, MemberIdentity, Payment, UserFlatMapping


class AnnouncementTarget(TypedDict):
    member_identity_id: UUID
    whatsapp_user_id: str
    receiver_name: str
    event_name: str | None
    preferred_language: str


class RecipientResolution(TypedDict):
    targets: list[AnnouncementTarget]
    total_candidates: int
    queued_count: int
    skipped_missing_whatsapp: int
    duplicate_whatsapp_ids: int


class AnnouncementRecipientService:

    @staticmethod
    def _resolve_whatsapp_targets(member_rows) -> RecipientResolution:
        targets: list[AnnouncementTarget] = []
        skipped_missing_whatsapp = 0
        duplicate_whatsapp_ids = 0
        seen_whatsapp_ids: set[str] = set()

        for row in member_rows:
            member_identity_id = getattr(row, "id", None)
            whatsapp_user_id = getattr(row, "whatsapp_user_id", None)

            if not member_identity_id:
                continue

            if not whatsapp_user_id:
                skipped_missing_whatsapp += 1
                continue

            if whatsapp_user_id in seen_whatsapp_ids:
                duplicate_whatsapp_ids += 1
                continue

            seen_whatsapp_ids.add(whatsapp_user_id)
            receiver_name = (
                getattr(row, "owner_name", None)
                or getattr(row, "normalized_identifier", None)
                or "Member"
            )
            event_name = getattr(row, "event_name", None)
            preferred_language = str(getattr(row, "preferred_language", "") or "").strip().lower() or "en"

            targets.append(
                {
                    "member_identity_id": cast(UUID, member_identity_id),
                    "whatsapp_user_id": whatsapp_user_id,
                    "receiver_name": str(receiver_name).strip(),
                    "event_name": str(event_name).strip() if event_name else None,
                    "preferred_language": preferred_language,
                }
            )

        return {
            "targets": targets,
            "total_candidates": len(member_rows),
            "queued_count": len(targets),
            "skipped_missing_whatsapp": skipped_missing_whatsapp,
            "duplicate_whatsapp_ids": duplicate_whatsapp_ids,
        }

    @staticmethod
    def get_event_joined_member_targets(db: Session, society_id, event_id) -> RecipientResolution:
        members = (
            db.query(
                MemberIdentity.id,
                MemberIdentity.whatsapp_user_id,
                MemberIdentity.normalized_identifier,
                MemberIdentity.preferred_language,
                Flat.owner_name,
                Event.name.label("event_name"),
            )
            .join(UserFlatMapping, UserFlatMapping.member_identity_id == MemberIdentity.id)
            .join(Flat, Flat.id == UserFlatMapping.flat_id)
            .join(Payment, Payment.flat_id == Flat.id)
            .join(Event, Event.id == Payment.event_id)
            .filter(
                Flat.society_id == society_id,
                Payment.event_id == event_id,
                Payment.status == "paid",
                UserFlatMapping.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        return AnnouncementRecipientService._resolve_whatsapp_targets(members)

    @staticmethod
    def get_active_member_targets(db: Session, society_id) -> RecipientResolution:
        members = (
            db.query(
                MemberIdentity.id,
                MemberIdentity.whatsapp_user_id,
                MemberIdentity.normalized_identifier,
                MemberIdentity.preferred_language,
                Flat.owner_name,
            )
            .join(UserFlatMapping, UserFlatMapping.member_identity_id == MemberIdentity.id)
            .join(Flat, Flat.id == UserFlatMapping.flat_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        return AnnouncementRecipientService._resolve_whatsapp_targets(members)
