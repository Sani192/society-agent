from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.models import EventFoodPass, EventFoodToken, Flat
from app.modules.events.food_collection_service import FoodCollectionService


class FoodPassOperationsReport:
    @staticmethod
    def generate(db: Session, event_id):
        dashboard = FoodCollectionService.dashboard(db=db, event_id=event_id, recent_limit=0)

        passes = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.is_participating.is_(True),
            )
            .all()
        )

        entitled_by_flat = defaultdict(int)
        for food_pass in passes:
            entitled_by_flat[food_pass.flat_id] += int(food_pass.veg_count or 0)
            entitled_by_flat[food_pass.flat_id] += int(food_pass.jain_count or 0)
            entitled_by_flat[food_pass.flat_id] += int(food_pass.kids_count or 0)

        token_flat_ids = {
            flat_id
            for flat_id, in db.query(EventFoodToken.flat_id)
            .filter(EventFoodToken.event_id == event_id)
            .distinct()
            .all()
            if flat_id is not None
        }
        event_flat_ids = set(entitled_by_flat.keys())
        event_flat_ids.update(token_flat_ids)

        flat_rows = []
        if event_flat_ids:
            flat_rows = (
                db.query(Flat.id, Flat.flat_number, Flat.block)
                .filter(Flat.id.in_(event_flat_ids))
                .all()
            )
        flat_meta = {flat_id: (flat_number, block) for flat_id, flat_number, block in flat_rows}

        per_flat_rows = []
        per_flat_summary = []
        for flat_id in sorted(event_flat_ids, key=lambda value: str(flat_meta.get(value, ("", ""))[0])):
            flat_status = FoodCollectionService.member_pass_status(
                db=db,
                event_id=event_id,
                flat_id=flat_id,
            )
            entitled = entitled_by_flat[flat_id]
            served_token = max(flat_status["served"] - flat_status["fallback_served"], 0)
            served_fallback = flat_status["fallback_served"]
            remaining = max(entitled - served_token - served_fallback, 0)
            flat_number, block = flat_meta.get(flat_id, ("-", "-"))

            summary_row = {
                "flat_id": str(flat_id),
                "flat_number": flat_number,
                "block": block,
                "entitled": entitled,
                "served_token": served_token,
                "served_fallback": served_fallback,
                "remaining": remaining,
            }
            per_flat_summary.append(summary_row)
            per_flat_rows.append(
                [
                    flat_number,
                    block,
                    entitled,
                    served_token,
                    served_fallback,
                    served_token + served_fallback,
                    remaining,
                ]
            )

        by_type = {
            key: value
            for key, value in dashboard["by_type"].items()
            if key != "fallback"
        }
        total_passes_generated = sum(item["total"] for item in by_type.values())

        return {
            "headers": [
                "Flat",
                "Block",
                "Entitled",
                "Served (Token)",
                "Served (Fallback)",
                "Served (Total)",
                "Remaining",
            ],
            "rows": per_flat_rows,
            "summary": {
                "total_passes_generated": total_passes_generated,
                "served_count": dashboard["served_plates"],
                "remaining_count": max(total_passes_generated - dashboard["served_plates"], 0),
                "fallback_serve_count": dashboard["by_type"].get("fallback", {}).get("served", 0),
                "by_food_type": by_type,
            },
            "per_flat_summary": per_flat_summary,
        }
