#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bootstrap all baseline seed data in one transaction."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from sqlalchemy import text

from app.config import settings
from app.db.models import (
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    Society,
)
from app.db.session import SessionLocal
from app.utils.identity import normalize_identifier
from seed_flats import seed_flats_without_commit
from seed_reminder_config import seed_reminder_config_without_commit

ADVISORY_LOCK_KEY = 82473011
BOOTSTRAP_GUARD_KEY = "initial_bootstrap"
BOOTSTRAP_GUARD_TABLE = "bootstrap_seed_guard"
DEFAULT_JOIN_CODE = "JOIN123"
DEFAULT_APPROVAL_REQUIRED = True
DEFAULT_WHATSAPP_EXTERNAL_USER_ID = "919999000000"


def seed_society(db) -> Society:
    society = (
        db.query(Society)
        .filter(Society.is_active.is_(True))
        .order_by(Society.created_at.asc())
        .first()
    )
    if society is not None:
        return _ensure_society_onboarding_config(db, society=society)

    society = Society(
        name=settings.DEFAULT_SOCIETY_NAME or "My Society",
        city=os.getenv("DEFAULT_SOCIETY_CITY", "Ahmedabad"),
        state=os.getenv("DEFAULT_SOCIETY_STATE", "Gujarat"),
        timezone=settings.TIMEZONE,
        config_json=_build_society_config(),
        is_active=True,
    )
    db.add(society)
    db.flush()
    return society


def seed_first_chairman(db, *, society: Society) -> CommitteeMember:
    chairman = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.society_id == society.id,
            CommitteeMember.role == "chairman",
            CommitteeMember.is_active.is_(True),
        )
        .order_by(CommitteeMember.created_at.asc())
        .first()
    )
    if chairman is not None:
        return chairman

    phone = os.getenv("BOOTSTRAP_CHAIRMAN_PHONE") or (
        settings.ADMIN_PHONE_WHITELIST[0] if settings.ADMIN_PHONE_WHITELIST else None
    )
    if not phone:
        raise ValueError("No chairman phone configured. Set BOOTSTRAP_CHAIRMAN_PHONE or ADMIN_PHONE_WHITELIST.")

    normalized_phone = normalize_identifier(phone)
    if not normalized_phone:
        raise ValueError("Invalid chairman phone configured.")

    chairman = CommitteeMember(
        society_id=society.id,
        name=os.getenv("BOOTSTRAP_CHAIRMAN_NAME", "Chairman"),
        phone_number=normalized_phone,
        role="chairman",
        is_active=True,
    )
    db.add(chairman)
    db.flush()
    return chairman


def seed_chairman_channel_identity(db, *, chairman: CommitteeMember) -> CommitteeMemberChannelIdentity:
    channel_type = "whatsapp"
    external_user_id = normalize_identifier(
        os.getenv("BOOTSTRAP_CHAIRMAN_EXTERNAL_USER_ID", chairman.phone_number)
    ) or normalize_identifier(chairman.phone_number) or DEFAULT_WHATSAPP_EXTERNAL_USER_ID
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


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _build_society_config() -> dict:
    join_code = (os.getenv("BOOTSTRAP_JOIN_CODE") or DEFAULT_JOIN_CODE).strip()
    if not join_code:
        join_code = DEFAULT_JOIN_CODE
    approval_required = _parse_bool(
        os.getenv("BOOTSTRAP_APPROVAL_REQUIRED"),
        default=DEFAULT_APPROVAL_REQUIRED,
    )
    return {
        "seed": "bootstrap",
        "onboarding": {
            "join_code": join_code,
            "approval_required": approval_required,
        },
    }


def _ensure_society_onboarding_config(db, *, society: Society) -> Society:
    config = dict(society.config_json or {})
    onboarding = dict(config.get("onboarding") or {})
    changed = False

    join_code = onboarding.get("join_code")
    if not isinstance(join_code, str) or not join_code.strip():
        onboarding["join_code"] = (os.getenv("BOOTSTRAP_JOIN_CODE") or DEFAULT_JOIN_CODE).strip() or DEFAULT_JOIN_CODE
        changed = True

    approval_required = onboarding.get("approval_required")
    if not isinstance(approval_required, bool):
        onboarding["approval_required"] = _parse_bool(
            os.getenv("BOOTSTRAP_APPROVAL_REQUIRED"),
            default=DEFAULT_APPROVAL_REQUIRED,
        )
        changed = True

    if changed:
        config["onboarding"] = onboarding
        society.config_json = config
        db.flush()
    return society


def _load_bootstrap_flats() -> Sequence[tuple[str, str, str]] | None:
    flats_file = (os.getenv("BOOTSTRAP_FLATS_FILE") or "").strip()
    if flats_file:
        flats: list[tuple[str, str, str]] = []
        with open(flats_file, encoding="utf-8") as handle:
            for line in handle:
                row = line.strip()
                if not row or row.startswith("#"):
                    continue
                parts = [part.strip() for part in row.split(",")]
                if len(parts) != 3:
                    raise ValueError(f"Invalid flat row in {flats_file}: {row}")
                flats.append((parts[0], parts[1], parts[2]))
        return tuple(flats)

    flats_list = (os.getenv("BOOTSTRAP_FLATS_LIST") or "").strip()
    if not flats_list:
        return None

    flats: list[tuple[str, str, str]] = []
    for row in flats_list.split(";"):
        cleaned = row.strip()
        if not cleaned:
            continue
        parts = [part.strip() for part in cleaned.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Invalid BOOTSTRAP_FLATS_LIST row: {cleaned}")
        flats.append((parts[0], parts[1], parts[2]))
    return tuple(flats)


def is_bootstrap_completed(db) -> bool:
    row = db.execute(
        text(f"SELECT 1 FROM {BOOTSTRAP_GUARD_TABLE} WHERE seed_key = :seed_key LIMIT 1"),
        {"seed_key": BOOTSTRAP_GUARD_KEY},
    ).first()
    return row is not None


def mark_bootstrap_completed(db) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO {BOOTSTRAP_GUARD_TABLE} (seed_key, completed_at)
            VALUES (:seed_key, NOW())
            ON CONFLICT (seed_key) DO NOTHING
            """
        ),
        {"seed_key": BOOTSTRAP_GUARD_KEY},
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
        flats_to_seed = _load_bootstrap_flats()
        if flats_to_seed is None:
            seed_flats_without_commit(db)
        else:
            seed_flats_without_commit(db, flats=flats_to_seed)

        stage = "seed reminder config"
        seed_reminder_config_without_commit(db)

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
