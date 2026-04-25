#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed flats for the first society when missing."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections.abc import Sequence
from typing import TypedDict

from app.db.models import Flat, Society
from app.db.session import SessionLocal

DEFAULT_FLATS: tuple[tuple[str, str, str], ...] = (("A-804", "A", "JK"),)


class SeedFlatsResult(TypedDict):
    created_count: int
    skipped_count: int


def seed_flats_without_commit(
    db,
    flats: Sequence[tuple[str, str, str]] = DEFAULT_FLATS,
) -> SeedFlatsResult:
    society = db.query(Society).first()
    if society is None:
        raise ValueError("No society found")

    created_count = 0
    skipped_count = 0
    for flat_no, block, owner_name in flats:
        exists = (
            db.query(Flat)
            .filter(Flat.flat_number == flat_no, Flat.society_id == society.id)
            .first()
        )
        if exists is None:
            db.add(
                Flat(
                    society_id=society.id,
                    flat_number=flat_no,
                    block=block,
                    owner_name=owner_name,
                )
            )
            created_count += 1
        else:
            skipped_count += 1

    return {"created_count": created_count, "skipped_count": skipped_count}


def seed_flats(db, flats: Sequence[tuple[str, str, str]] = DEFAULT_FLATS) -> int:
    result = seed_flats_without_commit(db, flats=flats)
    return result["created_count"]


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_flats_without_commit(db)
        db.commit()
        if result["created_count"]:
            print("✅ Flats seeded")
        else:
            print("ℹ️ Flats already seeded")
    finally:
        db.close()


if __name__ == "__main__":
    main()
