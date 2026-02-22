#!/usr/bin/env python3
"""Reset schema and seed deterministic baseline records for CI integration runs."""

from pathlib import Path
import sys

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.base import Base
from app.db.models import Flat, ReminderConfig, Society
from app.db.session import SessionLocal, engine


def reset_schema() -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

    Base.metadata.create_all(bind=engine)


def seed_baseline_data() -> None:
    db = SessionLocal()
    try:
        society = Society(
            name="CI Test Society",
            city="Bengaluru",
            state="Karnataka",
            timezone="Asia/Kolkata",
            config_json={"seed": "ci"},
            is_active=True,
        )
        db.add(society)
        db.flush()

        db.add(
            Flat(
                society_id=society.id,
                flat_number="A-101",
                block="A",
                owner_name="CI Owner",
                is_active=True,
            )
        )

        db.add(
            ReminderConfig(
                society_id=society.id,
                enabled=True,
                run_hour=10,
                run_minute=0,
                frequency="daily",
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    reset_schema()
    seed_baseline_data()
    print("✅ CI test database reset and seeded")
