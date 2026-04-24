#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bootstrap all baseline seed data in one transaction."""

from __future__ import annotations

import os
import sys

from sqlalchemy import text

from app.config import settings
from app.db.models import (
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    Society,
)
from app.db.session import SessionLocal
from seed_flats import seed_flats
from seed_reminder_config import seed_reminder_config

ADVISORY_LOCK_KEY = 82473011
BOOTSTRAP_RUN_KEY = "initial_bootstrap_v1"
BOOTSTRAP_RUNS_TABLE = "bootstrap_runs"


def seed_society(db) -> Society:
    society = db.query(Society).first()
    if society is not None:
        return society

    society = Society(
        name=settings.DEFAULT_SOCIETY_NAME or "My Society",
        city=os.getenv("DEFAULT_SOCIETY_CITY", "Ahmedabad"),
        state=os.getenv("DEFAULT_SOCIETY_STATE", "Gujarat"),
        timezone=settings.TIMEZONE,
        config_json={"seed": "bootstrap"},
        is_active=True,
    )
    db.add(society)
    db.flush()
    return society


def seed_first_chairman(db, *, society: Society) -> CommitteeMember:
    chairman = db.query(CommitteeMember).filter(CommitteeMember.role == "chairman").first()
    if chairman is not None:
        return chairman

    phone = os.getenv("BOOTSTRAP_CHAIRMAN_PHONE") or (settings.ADMIN_PHONE_WHITELIST[0] if settings.ADMIN_PHONE_WHITELIST else None)
    if not phone:
        raise ValueError("No chairman phone configured. Set BOOTSTRAP_CHAIRMAN_PHONE or ADMIN_PHONE_WHITELIST.")

    chairman = CommitteeMember(
        society_id=society.id,
        name=os.getenv("BOOTSTRAP_CHAIRMAN_NAME", "Chairman"),
        phone_number=phone,
        role="chairman",
        is_active=True,
    )
    db.add(chairman)
    db.flush()
    return chairman


def seed_chairman_channel_identity(db, *, chairman: CommitteeMember) -> CommitteeMemberChannelIdentity:
    channel_type = os.getenv("BOOTSTRAP_CHAIRMAN_CHANNEL", "whatsapp").strip().lower()
    external_user_id = os.getenv("BOOTSTRAP_CHAIRMAN_EXTERNAL_USER_ID", chairman.phone_number)
    username = os.getenv("BOOTSTRAP_CHAIRMAN_USERNAME")

    existing = (
        db.query(CommitteeMemberChannelIdentity)
        .filter(
            CommitteeMemberChannelIdentity.committee_member_id == chairman.id,
            CommitteeMemberChannelIdentity.channel_type == channel_type,
            CommitteeMemberChannelIdentity.external_user_id == external_user_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    identity = CommitteeMemberChannelIdentity(
        committee_member_id=chairman.id,
        channel_type=channel_type,
        external_user_id=external_user_id,
        username=username,
        is_verified=True,
    )
    db.add(identity)
    db.flush()
    return identity


def is_bootstrap_completed(db) -> bool:
    row = db.execute(
        text(
            f"""
            SELECT 1
            FROM {BOOTSTRAP_RUNS_TABLE}
            WHERE "key" = :key AND status = :status
            LIMIT 1
            """
        ),
        {"key": BOOTSTRAP_RUN_KEY, "status": "completed"},
    ).first()
    return row is not None


def mark_bootstrap_completed(db) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO {BOOTSTRAP_RUNS_TABLE} ("key", status, completed_at)
            VALUES (:key, :status, NOW())
            ON CONFLICT ("key") DO NOTHING
            """
        ),
        {"key": BOOTSTRAP_RUN_KEY, "status": "completed"},
    )


def main() -> int:
    db = SessionLocal()
    stage = "initialization"

    try:
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": ADVISORY_LOCK_KEY},
        )

        stage = "check guard"
        if is_bootstrap_completed(db):
            print("already seeded")
            db.rollback()
            return 0

        stage = "seed society"
        society = seed_society(db)

        stage = "seed first chairman"
        chairman = seed_first_chairman(db, society=society)

        stage = "seed chairman channel identity"
        seed_chairman_channel_identity(db, chairman=chairman)

        stage = "seed flats"
        seed_flats(db)

        stage = "seed reminder config"
        seed_reminder_config(db)

        stage = "mark bootstrap as completed"
        mark_bootstrap_completed(db)

        db.commit()
        print("bootstrap seed completed")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"bootstrap failed at stage '{stage}': {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
