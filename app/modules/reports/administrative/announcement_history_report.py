#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from app.db.models import Announcement


class AnnouncementHistoryReport:
    @staticmethod
    def generate(db, society_id):
        rows = (
            db.query(Announcement)
            .filter(Announcement.society_id == society_id)
            .order_by(Announcement.created_at.desc())
            .all()
        )

        return {
            "headers": [
                "announcement_id",
                "created_at",
                "type",
                "status",
                "message_preview",
                "event_id",
                "total_targets",
                "sent_count",
                "failed_count",
                "skipped_count",
            ],
            "rows": [
                [
                    str(row.id),
                    row.created_at.isoformat() if row.created_at else "",
                    row.type,
                    row.status,
                    (row.message_text or "")[:120],
                    str(row.event_id) if row.event_id else "",
                    int(getattr(row, "total_targets", 0) or 0),
                    int(getattr(row, "sent_count", 0) or 0),
                    int(getattr(row, "failed_count", 0) or 0),
                    int(getattr(row, "skipped_count", 0) or 0),
                ]
                for row in rows
            ],
        }
