#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Recipient targeting helpers for WhatsApp announcements."""

from sqlalchemy.orm import Session

from app.db.models import Flat, MemberIdentity, Payment, UserFlatMapping


class AnnouncementRecipientService:

    @staticmethod
    def _resolve_whatsapp_targets(member_rows) -> dict:
        targets: list[dict] = []
        skipped_missing_whatsapp = 0
        duplicate_whatsapp_ids = 0

        seen_whatsapp_ids: set[str] = set()

        for row in member_rows:
            member_identity_id = getattr(row, "id", None)
            whatsapp_user_id = getattr(row, "whatsapp_user_id", None)

            if not whatsapp_user_id:
                skipped_missing_whatsapp += 1
                continue

            if whatsapp_user_id in seen_whatsapp_ids:
                duplicate_whatsapp_ids += 1
                continue

            seen_whatsapp_ids.add(whatsapp_user_id)
            targets.append(
                {
                    "member_identity_id": str(member_identity_id),
                    "whatsapp_user_id": whatsapp_user_id,
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
    def get_event_joined_member_targets(db: Session, society_id, event_id) -> dict:
        members = (
            db.query(MemberIdentity.id, MemberIdentity.whatsapp_user_id)
            .join(UserFlatMapping, UserFlatMapping.member_identity_id == MemberIdentity.id)
            .join(Flat, Flat.id == UserFlatMapping.flat_id)
            .join(Payment, Payment.flat_id == Flat.id)
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
    def get_active_member_targets(db: Session, society_id) -> dict:
        members = (
            db.query(MemberIdentity.id, MemberIdentity.whatsapp_user_id)
            .join(UserFlatMapping, UserFlatMapping.member_identity_id == MemberIdentity.id)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        return AnnouncementRecipientService._resolve_whatsapp_targets(members)
