from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.db.models import AuditLog, EventFoodPass, EventFoodToken, Flat
from app.modules.events.food_collection_service import NO_TOKEN_FALLBACK_METHOD


class FoodPassOperationsReport:
    @staticmethod
    def generate(db: Session, event_id):
        passes = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.is_participating.is_(True),
            )
            .all()
        )
        tokens = db.query(EventFoodToken).filter(EventFoodToken.event_id == event_id).all()

        entitled_by_flat = defaultdict(int)
        for food_pass in passes:
            entitled_by_flat[food_pass.flat_id] += int(food_pass.veg_count or 0)
            entitled_by_flat[food_pass.flat_id] += int(food_pass.jain_count or 0)
            entitled_by_flat[food_pass.flat_id] += int(food_pass.kids_count or 0)

        served_token_by_flat = Counter(
            token.flat_id for token in tokens if token.flat_id is not None and token.served_at is not None
        )

        event_flat_ids = set(entitled_by_flat.keys())
        event_flat_ids.update(token.flat_id for token in tokens if token.flat_id is not None)

        fallback_audits = []
        if event_flat_ids:
            fallback_audits = (
                db.query(AuditLog)
                .filter(
                    AuditLog.entity_type == "food_collection",
                    AuditLog.action == NO_TOKEN_FALLBACK_METHOD,
                    AuditLog.entity_id.in_(event_flat_ids),
                )
                .all()
            )

        served_fallback_by_flat = Counter(audit.entity_id for audit in fallback_audits if audit.entity_id is not None)

        flat_rows = []
        if event_flat_ids:
            flat_rows = (
                db.query(Flat.id, Flat.flat_number, Flat.block)
                .filter(Flat.id.in_(event_flat_ids))
                .all()
            )
        flat_meta = {flat_id: (flat_number, block) for flat_id, flat_number, block in flat_rows}

        by_type_total = Counter(token.food_type for token in tokens)
        by_type_served = Counter(token.food_type for token in tokens if token.served_at is not None)

        per_flat_rows = []
        per_flat_summary = []
        for flat_id in sorted(event_flat_ids, key=lambda value: str(flat_meta.get(value, ("", "",))[0])):
            entitled = entitled_by_flat[flat_id]
            served_token = served_token_by_flat[flat_id]
            served_fallback = served_fallback_by_flat[flat_id]
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

        by_food_type = {
            food_type: {
                "total": by_type_total[food_type],
                "served": by_type_served[food_type],
                "remaining": by_type_total[food_type] - by_type_served[food_type],
            }
            for food_type in sorted(by_type_total.keys())
        }

        total_passes_generated = sum(by_type_total.values())
        fallback_serve_count = len(fallback_audits)
        total_served = sum(by_type_served.values()) + fallback_serve_count

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
                "served_count": total_served,
                "remaining_count": max(total_passes_generated - total_served, 0),
                "fallback_serve_count": fallback_serve_count,
                "by_food_type": by_food_type,
            },
            "per_flat_summary": per_flat_summary,
        }
