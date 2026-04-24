#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create reminder config if absent."""

from typing import TypedDict

from app.db.models import ReminderConfig, Society
from app.db.session import SessionLocal


class SeedReminderConfigResult(TypedDict):
    created_count: int
    skipped_count: int


def seed_reminder_config_without_commit(db) -> SeedReminderConfigResult:
    return seed_reminder_config_without_commit_with_defaults(
        db,
        enabled=True,
        run_hour=10,
        run_minute=0,
        frequency="daily",
    )


def seed_reminder_config_without_commit_with_defaults(
    db,
    *,
    enabled: bool,
    run_hour: int,
    run_minute: int,
    frequency: str,
) -> SeedReminderConfigResult:
    society = db.query(Society).first()
    if society is None:
        raise ValueError("No society found")

    existing = db.query(ReminderConfig).filter(ReminderConfig.society_id == society.id).first()
    if existing is not None:
        return {"created_count": 0, "skipped_count": 1}

    config = ReminderConfig(
        society_id=society.id,
        enabled=enabled,
        run_hour=run_hour,
        run_minute=run_minute,
        frequency=frequency,
    )
    db.add(config)
    return {"created_count": 1, "skipped_count": 0}


def seed_reminder_config(db) -> bool:
    result = seed_reminder_config_without_commit(db)
    return result["created_count"] > 0


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_reminder_config_without_commit(db)
        db.commit()
        if result["created_count"]:
            print("✅ Reminder config created")
        else:
            print("ℹ️ Reminder config already exists")
    finally:
        db.close()


if __name__ == "__main__":
    main()
