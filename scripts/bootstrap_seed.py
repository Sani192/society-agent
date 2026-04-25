#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bootstrap all baseline seed data in one transaction."""

from __future__ import annotations

import os
import sys

# Ensure the root project directory is on the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from collections.abc import Sequence
from typing import Any, Callable, TypeVar, cast

from sqlalchemy import text

from app.config import settings
from app.db.models import (
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    Society,
)
from app.db.session import SessionLocal
from app.utils.identity import normalize_identifier
from scripts.seed_flats import seed_flats_without_commit
from scripts.seed_reminder_config import seed_reminder_config_without_commit_with_defaults

ADVISORY_LOCK_KEY = 82473011
BOOTSTRAP_GUARD_KEY = "initial_bootstrap"
BOOTSTRAP_GUARD_TABLE = "bootstrap_seed_guard"
DEFAULT_JOIN_CODE = "JOIN123"
DEFAULT_APPROVAL_REQUIRED = True
DEFAULT_WHATSAPP_EXTERNAL_USER_ID = "919999000000"
DEFAULT_BOOTSTRAP_SEED_FILE = "bootstrap.seed.json"
T = TypeVar("T")


def _bootstrap_fail(message: str) -> ValueError:
    return ValueError(f"Invalid bootstrap config: {message}")


def _load_bootstrap_config() -> dict[str, Any] | None:
    configured_path = (os.getenv("BOOTSTRAP_SEED_FILE") or "").strip()
    bootstrap_seed_path = configured_path or DEFAULT_BOOTSTRAP_SEED_FILE
    if not configured_path and not os.path.exists(bootstrap_seed_path):
        return None

    try:
        with open(bootstrap_seed_path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:
        raise _bootstrap_fail(f"file not found: {bootstrap_seed_path}") from exc
    except json.JSONDecodeError as exc:
        raise _bootstrap_fail(f"failed to parse JSON from {bootstrap_seed_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise _bootstrap_fail("top-level JSON value must be an object")
    return raw


def _required_string(config: dict[str, Any], path: str) -> str:
    value: Any = config
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise _bootstrap_fail(f"missing required field '{path}'")
        value = value[key]
    if not isinstance(value, str) or not value.strip():
        raise _bootstrap_fail(f"field '{path}' must be a non-empty string")
    return value.strip()


def _optional_string(config: dict[str, Any], path: str) -> str | None:
    value: Any = config
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise _bootstrap_fail(f"field '{path}' must be a string")
    cleaned = value.strip()
    return cleaned or None


def _optional_bool(config: dict[str, Any], path: str) -> bool | None:
    value: Any = config
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if value is None:
        return None
    if not isinstance(value, bool):
        raise _bootstrap_fail(f"field '{path}' must be a boolean")
    return value


def _require_flats(config: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    raw = config.get("flats")
    if not isinstance(raw, list) or not raw:
        raise _bootstrap_fail("field 'flats' must be a non-empty array")
    parsed: list[tuple[str, str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise _bootstrap_fail(f"field 'flats[{index}]' must be an object")
        flat_number = _required_string({"item": item}, "item.flat_number")
        block = _required_string({"item": item}, "item.block")
        owner_name = _required_string({"item": item}, "item.owner_name")
        parsed.append((flat_number, block, owner_name))
    return tuple(parsed)


def _validated_bootstrap_overrides(config: dict[str, Any]) -> dict[str, Any]:
    reminder_frequency = _required_string(config, "reminder_defaults.frequency")
    if reminder_frequency not in {"daily", "weekly"}:
        raise _bootstrap_fail("field 'reminder_defaults.frequency' must be one of: daily, weekly")

    return {
        "society_name": _required_string(config, "society.name"),
        "society_city": _required_string(config, "society.city"),
        "society_state": _required_string(config, "society.state"),
        "society_timezone": _required_string(config, "society.timezone"),
        "join_code": _required_string(config, "onboarding.join_code"),
        "approval_required": _optional_bool(config, "onboarding.approval_required"),
        "chairman_name": _required_string(config, "chairman.name"),
        "chairman_phone": _required_string(config, "chairman.phone"),
        "channel_type": _optional_string(config, "chairman.channel_identity.channel_type") or "whatsapp",
        "external_user_id": _required_string(config, "chairman.channel_identity.external_user_id"),
        "username": _optional_string(config, "chairman.channel_identity.username"),
        "flats": _require_flats(config),
        "reminder_enabled": _optional_bool(config, "reminder_defaults.enabled"),
        "reminder_frequency": reminder_frequency,
        "reminder_run_hour": _required_int(config, "reminder_defaults.run_hour", min_value=0, max_value=23),
        "reminder_run_minute": _required_int(config, "reminder_defaults.run_minute", min_value=0, max_value=59),
    }


def _required_int(config: dict[str, Any], path: str, *, min_value: int, max_value: int) -> int:
    value: Any = config
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise _bootstrap_fail(f"missing required field '{path}'")
        value = value[key]
    if not isinstance(value, int):
        raise _bootstrap_fail(f"field '{path}' must be an integer")
    if not (min_value <= value <= max_value):
        raise _bootstrap_fail(f"field '{path}' must be between {min_value} and {max_value}")
    return value


def seed_society(db, *, overrides: dict[str, Any] | None = None) -> Society:
    society = (
        db.query(Society)
        .filter(Society.is_active.is_(True))
        .order_by(Society.created_at.asc())
        .first()
    )
    if society is not None:
        return _ensure_society_onboarding_config(db, society=society, overrides=overrides)

    society = Society(
        name=cast(str, (overrides or {}).get("society_name")) or settings.DEFAULT_SOCIETY_NAME or "My Society",
        city=cast(str, (overrides or {}).get("society_city")) or os.getenv("DEFAULT_SOCIETY_CITY", "Ahmedabad"),
        state=cast(str, (overrides or {}).get("society_state")) or os.getenv("DEFAULT_SOCIETY_STATE", "Gujarat"),
        timezone=cast(str, (overrides or {}).get("society_timezone")) or settings.TIMEZONE,
        config_json=_build_society_config(overrides=overrides),
        is_active=True,
    )
    db.add(society)
    db.flush()
    return society


def seed_first_chairman(db, *, society: Society, overrides: dict[str, Any] | None = None) -> CommitteeMember:
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

    phone = cast(str | None, (overrides or {}).get("chairman_phone")) or os.getenv("BOOTSTRAP_CHAIRMAN_PHONE") or (
        settings.ADMIN_PHONE_WHITELIST[0] if settings.ADMIN_PHONE_WHITELIST else None
    )
    if not phone:
        raise ValueError("No chairman phone configured. Set BOOTSTRAP_CHAIRMAN_PHONE or ADMIN_PHONE_WHITELIST.")

    normalized_phone = normalize_identifier(phone)
    if not normalized_phone:
        raise ValueError("Invalid chairman phone configured.")

    chairman = CommitteeMember(
        society_id=society.id,
        name=cast(str | None, (overrides or {}).get("chairman_name"))
        or os.getenv("BOOTSTRAP_CHAIRMAN_NAME", "Chairman"),
        phone_number=normalized_phone,
        role="chairman",
        is_active=True,
    )
    db.add(chairman)
    db.flush()
    return chairman


def seed_chairman_channel_identity(
    db,
    *,
    chairman: CommitteeMember,
    overrides: dict[str, Any] | None = None,
) -> CommitteeMemberChannelIdentity:
    channel_type = cast(str, (overrides or {}).get("channel_type")) or "whatsapp"
    chairman_phone = cast(str | None, getattr(chairman, "phone_number", None))
    external_user_id = normalize_identifier(
        cast(str | None, (overrides or {}).get("external_user_id"))
        or os.getenv("BOOTSTRAP_CHAIRMAN_EXTERNAL_USER_ID", chairman_phone)
    ) or normalize_identifier(chairman_phone) or DEFAULT_WHATSAPP_EXTERNAL_USER_ID
    username = cast(str | None, (overrides or {}).get("username")) or os.getenv("BOOTSTRAP_CHAIRMAN_USERNAME")

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


def _build_society_config(*, overrides: dict[str, Any] | None = None) -> dict:
    join_code = (
        cast(str | None, (overrides or {}).get("join_code"))
        or os.getenv("BOOTSTRAP_JOIN_CODE")
        or DEFAULT_JOIN_CODE
    ).strip()
    if not join_code:
        join_code = DEFAULT_JOIN_CODE
    override_approval_required = cast(bool | None, (overrides or {}).get("approval_required"))
    approval_required = (
        override_approval_required
        if override_approval_required is not None
        else _parse_bool(
            os.getenv("BOOTSTRAP_APPROVAL_REQUIRED"),
            default=DEFAULT_APPROVAL_REQUIRED,
        )
    )
    return {
        "seed": "bootstrap",
        "onboarding": {
            "join_code": join_code,
            "approval_required": approval_required,
        },
    }


def _ensure_society_onboarding_config(
    db,
    *,
    society: Society,
    overrides: dict[str, Any] | None = None,
) -> Society:
    config: dict[str, Any] = dict(cast(dict[str, Any] | None, getattr(society, "config_json", None)) or {})
    onboarding: dict[str, Any] = dict(cast(dict[str, Any] | None, config.get("onboarding")) or {})
    changed = False

    join_code = onboarding.get("join_code")
    if not isinstance(join_code, str) or not join_code.strip():
        onboarding["join_code"] = (
            cast(str | None, (overrides or {}).get("join_code"))
            or os.getenv("BOOTSTRAP_JOIN_CODE")
            or DEFAULT_JOIN_CODE
        ).strip() or DEFAULT_JOIN_CODE
        changed = True

    approval_required = onboarding.get("approval_required")
    if not isinstance(approval_required, bool):
        override_approval_required = cast(bool | None, (overrides or {}).get("approval_required"))
        onboarding["approval_required"] = (
            override_approval_required
            if override_approval_required is not None
            else _parse_bool(
                os.getenv("BOOTSTRAP_APPROVAL_REQUIRED"),
                default=DEFAULT_APPROVAL_REQUIRED,
            )
        )
        changed = True

    if changed:
        config["onboarding"] = onboarding
        setattr(society, "config_json", config)
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

    parsed_flats: list[tuple[str, str, str]] = []
    for row in flats_list.split(";"):
        cleaned = row.strip()
        if not cleaned:
            continue
        parts = [part.strip() for part in cleaned.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Invalid BOOTSTRAP_FLATS_LIST row: {cleaned}")
        parsed_flats.append((parts[0], parts[1], parts[2]))
    return tuple(parsed_flats)


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


def _log_stage_start(stage: str) -> None:
    print(f"START {stage}")


def _log_stage_success(stage: str) -> None:
    print(f"SUCCESS {stage}")


def _log_stage_fail(stage: str) -> None:
    print(f"FAIL {stage}", file=sys.stderr)


def _run_stage(stage: str, action: Callable[[], T]) -> T:
    _log_stage_start(stage)
    try:
        result = action()
    except Exception:
        _log_stage_fail(stage)
        raise
    _log_stage_success(stage)
    return result


def _verify_seeded_data(
    db,
    *,
    society_id: int,
    chairman_id: int,
    include_global_diagnostics: bool = True,
) -> None:
    scoped_society_exists = cast(
        bool,
        db.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM societies
                    WHERE id = :society_id AND is_active = TRUE
                )
                """
            ),
            {"society_id": society_id},
        ).scalar_one(),
    )
    if not scoped_society_exists:
        raise ValueError(f"Verification failed: active society not found for society_id={society_id}")

    scoped_chairman_exists = cast(
        bool,
        db.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM committee_members
                    WHERE id = :chairman_id
                      AND society_id = :society_id
                      AND role = 'chairman'
                      AND is_active = TRUE
                )
                """
            ),
            {"society_id": society_id, "chairman_id": chairman_id},
        ).scalar_one(),
    )
    if not scoped_chairman_exists:
        raise ValueError(
            "Verification failed: active chairman not found for "
            f"chairman_id={chairman_id}, society_id={society_id}"
        )

    scoped_chairman_identity_exists = cast(
        bool,
        db.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM committee_member_channel_identities
                    WHERE committee_member_id = :chairman_id
                )
                """
            ),
            {"chairman_id": chairman_id},
        ).scalar_one(),
    )
    if not scoped_chairman_identity_exists:
        raise ValueError(
            "Verification failed: chairman channel identity not found for "
            f"chairman_id={chairman_id}"
        )

    scoped_flats_exist = cast(
        bool,
        db.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM flats
                    WHERE society_id = :society_id
                )
                """
            ),
            {"society_id": society_id},
        ).scalar_one(),
    )
    if not scoped_flats_exist:
        raise ValueError(f"Verification failed: flats not found for society_id={society_id}")

    scoped_reminder_config_exists = cast(
        bool,
        db.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM reminder_configs
                    WHERE society_id = :society_id
                )
                """
            ),
            {"society_id": society_id},
        ).scalar_one(),
    )
    if not scoped_reminder_config_exists:
        raise ValueError(f"Verification failed: reminder config not found for society_id={society_id}")

    if include_global_diagnostics:
        society_count = cast(int, db.execute(text("SELECT COUNT(*) FROM societies")).scalar_one())
        active_chairman_count = cast(
            int,
            db.execute(
                text("SELECT COUNT(*) FROM committee_members WHERE role = 'chairman' AND is_active = TRUE")
            ).scalar_one(),
        )
        chairman_identity_count = cast(
            int,
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM committee_members cm
                    INNER JOIN committee_member_channel_identities ci
                        ON ci.committee_member_id = cm.id
                    WHERE cm.role = 'chairman' AND cm.is_active = TRUE
                    """
                )
            ).scalar_one(),
        )
        flats_count = cast(int, db.execute(text("SELECT COUNT(*) FROM flats")).scalar_one())
        reminder_config_count = cast(int, db.execute(text("SELECT COUNT(*) FROM reminder_configs")).scalar_one())
        print(
            "Diagnostic global counts: "
            f"societies={society_count}, "
            f"active_chairmen={active_chairman_count}, "
            f"chairman_identities={chairman_identity_count}, "
            f"flats={flats_count}, "
            f"reminder_configs={reminder_config_count}"
        )


def main() -> int:
    stage = "load bootstrap config"
    db = None
    bootstrap_overrides = None

    try:
        raw_config = _load_bootstrap_config()
        if raw_config is not None:
            bootstrap_overrides = _validated_bootstrap_overrides(raw_config)

        stage = "initialization"

        def _initialize() -> Any:
            nonlocal db
            db = SessionLocal()
            db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": ADVISORY_LOCK_KEY},
            )
            return db

        _run_stage(stage, _initialize)
        if db is None:
            raise RuntimeError("Database session initialization failed")

        stage = "check guard"
        if _run_stage(stage, lambda: is_bootstrap_completed(db)):
            print("already seeded")
            db.rollback()
            return 0

        stage = "seed society"
        society = _run_stage(stage, lambda: seed_society(db, overrides=bootstrap_overrides))

        stage = "seed first chairman"
        chairman = _run_stage(stage, lambda: seed_first_chairman(db, society=society, overrides=bootstrap_overrides))

        stage = "seed chairman channel identity"
        _run_stage(stage, lambda: seed_chairman_channel_identity(db, chairman=chairman, overrides=bootstrap_overrides))

        stage = "seed flats"
        flats_to_seed = cast(Sequence[tuple[str, str, str]] | None, (bootstrap_overrides or {}).get("flats"))
        if flats_to_seed is None:
            flats_to_seed = _load_bootstrap_flats()
        if flats_to_seed is None:
            _run_stage(stage, lambda: seed_flats_without_commit(db))
        else:
            _run_stage(stage, lambda: seed_flats_without_commit(db, flats=flats_to_seed))

        stage = "seed reminder config"
        def _seed_reminder_config() -> Any:
            reminder_enabled = cast(bool | None, (bootstrap_overrides or {}).get("reminder_enabled"))
            return seed_reminder_config_without_commit_with_defaults(
                db,
                enabled=True if reminder_enabled is None else reminder_enabled,
                run_hour=cast(int, (bootstrap_overrides or {}).get("reminder_run_hour")) if bootstrap_overrides else 10,
                run_minute=cast(int, (bootstrap_overrides or {}).get("reminder_run_minute")) if bootstrap_overrides else 0,
                frequency=cast(str, (bootstrap_overrides or {}).get("reminder_frequency")) if bootstrap_overrides else "daily",
            )

        _run_stage(stage, _seed_reminder_config)

        stage = "verify seeded data"
        def _flush_and_verify():
            db.flush()
            _verify_seeded_data(
                db,
                society_id=cast(int, society.id),
                chairman_id=cast(int, chairman.id),
            )
        _run_stage(stage, _flush_and_verify)

        stage = "mark bootstrap as completed"
        _run_stage(stage, lambda: mark_bootstrap_completed(db))

        db.commit()
        print("bootstrap seed completed")
        return 0
    except Exception as exc:  # noqa: BLE001
        if db is not None:
            db.rollback()
        print(f"bootstrap failed at stage '{stage}': {exc}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
