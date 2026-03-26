#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Refund, Flat, CommitteeMember
from app.i18n.catalog import translate
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class MemberRefundReport:
    @staticmethod
    def iter_rows(db: Session, *, event_id, lang: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None, chunk_size: int = 500):
        query = (
            db.query(
                Flat.flat_number,
                Refund.amount,
                Refund.reason,
                Refund.created_at,
                CommitteeMember.name.label("created_by")
            )
            .join(Flat, Flat.id == Refund.flat_id)
            .outerjoin(CommitteeMember, CommitteeMember.id == Refund.created_by)
            .filter(Refund.event_id == event_id, Refund.status.in_(["approved", "refunded"]))
            .order_by(Refund.created_at.asc())
        )
        if start_date:
            query = query.filter(Refund.created_at >= start_date)
        if end_date:
            query = query.filter(Refund.created_at <= end_date)

        for flat_number, amount, reason, created_at, created_by in query.yield_per(chunk_size):
            yield [flat_number, amount, reason, format_timestamp(created_at), created_by or translate("report_exports.labels.system", lang)]

    @staticmethod
    @log_service_call(logger, "MemberRefundReport.generate")
    def generate(db: Session, *, event_id, lang: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None):
        context = build_log_context(event_id=event_id)
        rows = list(MemberRefundReport.iter_rows(db, event_id=event_id, lang=lang, start_date=start_date, end_date=end_date))
        if not rows:
            logger.info("Workflow decision: no member refunds found | context=%s", context)

        return {
            "header_keys": ["flat", "refund_amount", "reason", "created_at", "created_by"],
            "headers": [
                translate("report_exports.labels.headers.flat", lang),
                translate("report_exports.labels.headers.refund_amount", lang),
                translate("report_exports.labels.headers.reason", lang),
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.created_by", lang),
            ],
            "rows": rows,
        }
