from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditLog, ChannelDeadLetter, ChannelMessageEvent


class AuditRetentionService:
    @staticmethod
    def prune(db: Session) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        deleted_by_event: dict[str, int] = {}

        for event_type, days in settings.AUDIT_RETENTION_DAYS_BY_EVENT.items():
            cutoff = now - timedelta(days=int(days))
            deleted = (
                db.query(ChannelMessageEvent)
                .filter(
                    ChannelMessageEvent.event_type == event_type,
                    ChannelMessageEvent.occurred_at < cutoff,
                )
                .delete(synchronize_session=False)
            )
            deleted_by_event[event_type] = int(deleted or 0)

        dead_letter_cutoff_days = max(settings.AUDIT_RETENTION_DAYS_BY_EVENT.values(), default=90)
        dead_letter_cutoff = now - timedelta(days=int(dead_letter_cutoff_days))
        dead_letters_deleted = (
            db.query(ChannelDeadLetter)
            .filter(ChannelDeadLetter.occurred_at < dead_letter_cutoff)
            .delete(synchronize_session=False)
        )

        governance_cutoff_days = max(dead_letter_cutoff_days, 365)
        governance_cutoff = now - timedelta(days=governance_cutoff_days)
        audit_logs_deleted = (
            db.query(AuditLog)
            .filter(AuditLog.performed_at < governance_cutoff)
            .delete(synchronize_session=False)
        )

        db.commit()
        deleted_by_event["channel_dead_letters"] = int(dead_letters_deleted or 0)
        deleted_by_event["audit_logs"] = int(audit_logs_deleted or 0)
        return deleted_by_event
