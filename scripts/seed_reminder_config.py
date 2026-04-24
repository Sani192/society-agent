#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create reminder config if absent."""

from app.db.models import ReminderConfig, Society
from app.db.session import SessionLocal


def seed_reminder_config(db) -> bool:
    society = db.query(Society).first()
    if society is None:
        raise ValueError("No society found")

    existing = db.query(ReminderConfig).filter(ReminderConfig.society_id == society.id).first()
    if existing is not None:
        return False

    config = ReminderConfig(
        society_id=society.id,
        enabled=True,
        run_hour=10,
        run_minute=0,
        frequency="daily",
    )
    db.add(config)
    return True


def main() -> None:
    db = SessionLocal()
    try:
        created = seed_reminder_config(db)
        db.commit()
        if created:
            print("✅ Reminder config created")
        else:
            print("ℹ️ Reminder config already exists")
    finally:
        db.close()


if __name__ == "__main__":
    main()
