#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Map a known user identifier to a flat."""

from app.db.models import Flat, Society
from app.db.session import SessionLocal
from app.modules.users.user_flat_service import UserFlatService


def map_user_to_flat(
    db,
    *,
    user_identifier: str,
    flat_number: str,
) -> None:
    society = db.query(Society).first()
    if society is None:
        raise ValueError("No society found")

    flat = (
        db.query(Flat)
        .filter(Flat.flat_number == flat_number, Flat.society_id == society.id)
        .first()
    )
    if flat is None:
        raise ValueError(f"Flat not found: {flat_number}")

    UserFlatService.assign_user_to_flat(
        db=db,
        society_id=society.id,
        flat_id=flat.id,
        user_identifier=user_identifier,
    )


def main() -> None:
    db = SessionLocal()
    try:
        map_user_to_flat(db, user_identifier="913333333333", flat_number="E-303")
        print("✅ User mapped to flat")
    finally:
        db.close()


if __name__ == "__main__":
    main()
