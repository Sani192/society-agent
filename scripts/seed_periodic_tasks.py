#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create default periodic tasks if absent."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict

from app.db.models import PeriodicTask, Society
from app.db.session import SessionLocal


class SeedPeriodicTaskResult(TypedDict):
    created_count: int
    skipped_count: int


def seed_periodic_tasks_without_commit(db) -> SeedPeriodicTaskResult:
    society = db.query(Society).first()
    if society is None:
        raise ValueError("No society found")

    tasks_to_create = [
        {
            "name": "payment_reminders",
            "task_function": "app.modules.reminders.reminder_scheduler.run_payment_reminders",
            "kwargs_json": {"society_id": str(society.id)},
            "schedule_type": "cron",
            "cron_hour": "10",
            "cron_minute": "0",
        },
        {
            "name": "event_auto_close",
            "task_function": "app.modules.reminders.reminder_scheduler.run_event_auto_close_job",
            "kwargs_json": {"society_id": str(society.id)},
            "schedule_type": "cron",
            "cron_hour": "10",
            "cron_minute": "0",
        },
        {
            "name": "audit_retention_prune",
            "task_function": "app.modules.reminders.reminder_scheduler.run_audit_retention_prune",
            "kwargs_json": {},
            "schedule_type": "cron",
            "cron_hour": "3",
            "cron_minute": "15",
        },
        {
            "name": "announcement_delivery_dispatch",
            "task_function": "app.modules.announcements.delivery_worker.run_pending_announcement_deliveries",
            "kwargs_json": {},
            "schedule_type": "interval",
            "interval_seconds": 30,
        }
    ]

    created = 0
    skipped = 0

    for task_data in tasks_to_create:
        existing = db.query(PeriodicTask).filter(PeriodicTask.name == task_data["name"]).first()
        if existing:
            skipped += 1
            continue

        task = PeriodicTask(
            name=task_data["name"],
            task_function=task_data["task_function"],
            kwargs_json=task_data["kwargs_json"],
            schedule_type=task_data["schedule_type"],
            cron_hour=task_data.get("cron_hour"),
            cron_minute=task_data.get("cron_minute"),
            interval_seconds=task_data.get("interval_seconds"),
            enabled=True
        )
        db.add(task)
        created += 1

    return {"created_count": created, "skipped_count": skipped}


def seed_periodic_tasks(db) -> bool:
    result = seed_periodic_tasks_without_commit(db)
    return result["created_count"] > 0


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_periodic_tasks_without_commit(db)
        db.commit()
        if result["created_count"]:
            print(f"✅ {result['created_count']} periodic tasks created")
        if result["skipped_count"]:
            print(f"ℹ️ {result['skipped_count']} periodic tasks already exist")
    finally:
        db.close()


if __name__ == "__main__":
    main()
