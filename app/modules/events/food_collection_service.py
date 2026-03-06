#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
from collections import Counter
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Event, EventFoodCounter, EventFoodPass, EventFoodToken, Flat
from app.utils.time import utc_now

TOKEN_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
SERVE_METHODS = {"QR_SCAN", "MANUAL_TOKEN", "FLAT_LOOKUP"}


class FoodCollectionService:

    @staticmethod
    def _build_token_code(*, existing_codes: set[str], length: int = 6) -> str:
        while True:
            token = "".join(random.choice(TOKEN_ALPHABET) for _ in range(length))
            if token not in existing_codes:
                existing_codes.add(token)
                return token

    @staticmethod
    def generate_tokens_for_event(
        db: Session,
        *,
        event_id,
        performed_by,
        notify_callback=None,
        token_length: int = 6,
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        existing_count = (
            db.query(func.count(EventFoodToken.id))
            .filter(EventFoodToken.event_id == event_id)
            .scalar()
        )
        if existing_count and existing_count > 0:
            raise Exception("Food tokens already generated for this event")

        passes = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.is_participating.is_(True),
            )
            .all()
        )

        token_rows: list[EventFoodToken] = []
        token_codes: set[str] = set()

        for food_pass in passes:
            token_plan = {
                "veg": food_pass.veg_count,
                "jain": food_pass.jain_count,
                "kids": food_pass.kids_count,
            }
            for food_type, count in token_plan.items():
                for _ in range(max(count, 0)):
                    code = FoodCollectionService._build_token_code(
                        existing_codes=token_codes,
                        length=token_length,
                    )
                    token_rows.append(
                        EventFoodToken(
                            event_id=event_id,
                            flat_id=food_pass.flat_id,
                            food_type=food_type,
                            token_code=code,
                            qr_payload=f"DFP:{event_id}:{code}",
                        )
                    )

        for row in token_rows:
            db.add(row)

        db.add(
            AuditLog(
                society_id=event.society_id,
                entity_type="food_collection",
                entity_id=event_id,
                action="GENERATE_FOOD_TOKENS",
                reason=f"Generated {len(token_rows)} tokens",
                performed_by=performed_by,
            )
        )

        if notify_callback is not None:
            notify_callback(event=event, generated_tokens=token_rows)

        db.commit()
        return token_rows

    @staticmethod
    def open_food_counter(
        db: Session,
        *,
        event_id,
        performed_by,
        auto_close_minutes: int = 120,
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        now = utc_now()
        counter = db.query(EventFoodCounter).filter(EventFoodCounter.event_id == event_id).first()
        if not counter:
            counter = EventFoodCounter(event_id=event_id)
            db.add(counter)

        counter.is_open = True
        counter.opened_at = now
        counter.closed_at = None
        counter.opened_by = performed_by
        counter.closed_by = None
        counter.closes_at = now + timedelta(minutes=auto_close_minutes)
        counter.updated_at = now

        db.add(
            AuditLog(
                society_id=event.society_id,
                entity_type="food_collection",
                entity_id=event_id,
                action="OPEN_FOOD_COUNTER",
                reason=f"Auto-close in {auto_close_minutes} minutes",
                performed_by=performed_by,
            )
        )

        db.commit()
        return counter

    @staticmethod
    def _close_counter_if_expired(db: Session, *, event, counter, performed_by=None):
        if not counter or not counter.is_open:
            return False
        if counter.closes_at and utc_now() > counter.closes_at:
            counter.is_open = False
            counter.closed_at = utc_now()
            counter.closed_by = performed_by
            counter.updated_at = utc_now()
            db.add(
                AuditLog(
                    society_id=event.society_id,
                    entity_type="food_collection",
                    entity_id=event.id,
                    action="AUTO_CLOSE_FOOD_COUNTER",
                    reason="Counter auto-closed after configured duration",
                    performed_by=performed_by,
                )
            )
            db.commit()
            return True
        return False

    @staticmethod
    def verify_and_serve_token(
        db: Session,
        *,
        event_id,
        token_code: str,
        method: str,
        performed_by,
    ):
        normalized_method = (method or "").strip().upper()
        if normalized_method not in SERVE_METHODS:
            raise Exception("Invalid serving method")

        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        counter = db.query(EventFoodCounter).filter(EventFoodCounter.event_id == event_id).first()
        if not counter or not counter.is_open:
            raise Exception("Food counter is closed")

        if FoodCollectionService._close_counter_if_expired(
            db,
            event=event,
            counter=counter,
            performed_by=performed_by,
        ):
            raise Exception("Food service has ended")

        token = (
            db.query(EventFoodToken)
            .filter(
                EventFoodToken.event_id == event_id,
                EventFoodToken.token_code == (token_code or "").strip().upper(),
            )
            .first()
        )

        if not token:
            db.add(
                AuditLog(
                    society_id=event.society_id,
                    entity_type="food_collection",
                    entity_id=event_id,
                    action="REJECT_FOOD_TOKEN",
                    reason=f"Token not found: {(token_code or '').strip().upper()}",
                    performed_by=performed_by,
                )
            )
            db.commit()
            raise Exception("Invalid token")

        if token.served_at is not None:
            db.add(
                AuditLog(
                    society_id=event.society_id,
                    entity_type="food_collection",
                    entity_id=token.id,
                    action="REJECT_FOOD_TOKEN",
                    reason=f"Already served via {token.served_method}",
                    performed_by=performed_by,
                )
            )
            db.commit()
            raise Exception("Token already used")

        token.served_at = utc_now()
        token.served_method = normalized_method
        token.served_by = performed_by

        db.add(
            AuditLog(
                society_id=event.society_id,
                entity_type="food_collection",
                entity_id=token.id,
                action="SERVE_FOOD_TOKEN",
                reason=f"Served via {normalized_method}",
                performed_by=performed_by,
            )
        )

        db.commit()
        return token

    @staticmethod
    def serve_by_flat_lookup(db: Session, *, event_id, flat_id, performed_by):
        token = (
            db.query(EventFoodToken)
            .filter(
                EventFoodToken.event_id == event_id,
                EventFoodToken.flat_id == flat_id,
                EventFoodToken.served_at.is_(None),
            )
            .order_by(EventFoodToken.created_at.asc())
            .first()
        )
        if not token:
            raise Exception("No remaining tokens for this flat")
        return FoodCollectionService.verify_and_serve_token(
            db=db,
            event_id=event_id,
            token_code=token.token_code,
            method="FLAT_LOOKUP",
            performed_by=performed_by,
        )

    @staticmethod
    def member_pass_status(db: Session, *, event_id, flat_id):
        rows = (
            db.query(EventFoodToken)
            .filter(
                EventFoodToken.event_id == event_id,
                EventFoodToken.flat_id == flat_id,
            )
            .all()
        )

        totals = Counter(row.food_type for row in rows)
        served = Counter(row.food_type for row in rows if row.served_at is not None)

        return {
            "total_passes": len(rows),
            "served": sum(served.values()),
            "remaining": len(rows) - sum(served.values()),
            "by_type": {
                food_type: {
                    "total": totals[food_type],
                    "served": served[food_type],
                    "remaining": totals[food_type] - served[food_type],
                }
                for food_type in sorted(totals.keys())
            },
            "tokens": [
                {
                    "token": row.token_code,
                    "food_type": row.food_type,
                    "served": row.served_at is not None,
                }
                for row in rows
            ],
        }

    @staticmethod
    def committee_flat_status(db: Session, *, event_id, flat_number: str):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == event.society_id,
            )
            .first()
        )
        if not flat:
            raise Exception("Flat not found")
        summary = FoodCollectionService.member_pass_status(db=db, event_id=event_id, flat_id=flat.id)
        summary["flat_number"] = flat.flat_number
        return summary

    @staticmethod
    def inspect_token(db: Session, *, event_id, token_code: str):
        token = (
            db.query(EventFoodToken)
            .filter(
                EventFoodToken.event_id == event_id,
                EventFoodToken.token_code == (token_code or "").strip().upper(),
            )
            .first()
        )
        if not token:
            raise Exception("Token not found")
        return token

    @staticmethod
    def dashboard(db: Session, *, event_id, recent_limit: int = 10):
        tokens = db.query(EventFoodToken).filter(EventFoodToken.event_id == event_id).all()
        served_tokens = [row for row in tokens if row.served_at is not None]

        by_type_total = Counter(row.food_type for row in tokens)
        by_type_served = Counter(row.food_type for row in served_tokens)

        recent = (
            sorted(served_tokens, key=lambda row: row.served_at, reverse=True)[:recent_limit]
            if served_tokens
            else []
        )

        return {
            "total_plates": len(tokens),
            "served_plates": len(served_tokens),
            "remaining_plates": len(tokens) - len(served_tokens),
            "by_type": {
                food_type: {
                    "total": by_type_total[food_type],
                    "served": by_type_served[food_type],
                    "remaining": by_type_total[food_type] - by_type_served[food_type],
                }
                for food_type in sorted(by_type_total.keys())
            },
            "recent_served": [
                {
                    "token": row.token_code,
                    "flat_id": row.flat_id,
                    "food_type": row.food_type,
                    "served_at": row.served_at,
                }
                for row in recent
            ],
        }
