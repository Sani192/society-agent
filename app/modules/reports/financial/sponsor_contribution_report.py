#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import EventContribution, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class SponsorContributionReport:
    headers = [
        "Contribution Type",
        "Source",
        "Contribution Code",
        "Flat",
        "Cash Amount",
        "In-kind Contribution",
        "Created At",
        "Created By"
    ]

    @staticmethod
    def iter_rows(db: Session, event_id, *, start_date: datetime | None = None, end_date: datetime | None = None, chunk_size: int = 500):
        query = (
            db.query(
                EventContribution.contribution_type,
                EventContribution.source_name,
                EventContribution.contribution_code,
                Flat.flat_number,
                EventContribution.amount,
                EventContribution.in_kind_details,
                EventContribution.created_at,
            )
            .outerjoin(Flat, Flat.id == EventContribution.flat_id)
            .filter(EventContribution.event_id == event_id)
            .order_by(EventContribution.created_at.asc())
        )
        if start_date:
            query = query.filter(EventContribution.created_at >= start_date)
        if end_date:
            query = query.filter(EventContribution.created_at <= end_date)

        for ctype, source, code, flat, amount, in_kind, created_at in query.yield_per(chunk_size):
            yield [ctype, source, code, flat or "-", amount or 0, in_kind or "-", format_timestamp(created_at), "System"]

    @staticmethod
    @log_service_call(logger, "SponsorContributionReport.generate")
    def generate(db: Session, event_id, *, start_date: datetime | None = None, end_date: datetime | None = None):
        context = build_log_context(event_id=event_id)
        rows = list(SponsorContributionReport.iter_rows(db, event_id, start_date=start_date, end_date=end_date))

        total_cash_query = db.query(func.coalesce(func.sum(EventContribution.amount), 0)).filter(EventContribution.event_id == event_id)
        if start_date:
            total_cash_query = total_cash_query.filter(EventContribution.created_at >= start_date)
        if end_date:
            total_cash_query = total_cash_query.filter(EventContribution.created_at <= end_date)
        total_cash = total_cash_query.scalar() or 0

        if not rows:
            logger.info("Workflow decision: sponsor contribution report empty | context=%s", context)
        return {"headers": SponsorContributionReport.headers, "rows": rows, "total_cash": total_cash}
