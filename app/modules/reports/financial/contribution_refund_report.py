#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import ContributionRefund, EventContribution
from app.i18n.catalog import translate
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class ContributionRefundReport:
    @staticmethod
    def iter_rows(db: Session, event_id, *, lang: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None, chunk_size: int = 500):
        query = (
            db.query(
                EventContribution.contribution_type,
                EventContribution.source_name,
                ContributionRefund.amount,
                ContributionRefund.reason,
                ContributionRefund.status,
                ContributionRefund.processed_at,
            )
            .join(EventContribution, EventContribution.id == ContributionRefund.contribution_id)
            .filter(EventContribution.event_id == event_id)
            .order_by(ContributionRefund.processed_at.asc())
        )
        if start_date:
            query = query.filter(ContributionRefund.processed_at >= start_date)
        if end_date:
            query = query.filter(ContributionRefund.processed_at <= end_date)

        for ctype, source, amount, reason, status, processed_at in query.yield_per(chunk_size):
            yield [ctype, source, amount or 0, reason, status, format_timestamp(processed_at), translate("report_exports.labels.system", lang)]

    @staticmethod
    @log_service_call(logger, "ContributionRefundReport.generate")
    def generate(db: Session, event_id, *, lang: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None):
        context = build_log_context(event_id=event_id)
        rows = list(ContributionRefundReport.iter_rows(db, event_id, lang=lang, start_date=start_date, end_date=end_date))

        total_refunded_query = (
            db.query(func.coalesce(func.sum(ContributionRefund.amount), 0))
            .join(EventContribution, EventContribution.id == ContributionRefund.contribution_id)
            .filter(EventContribution.event_id == event_id, ContributionRefund.status == "refunded")
        )
        if start_date:
            total_refunded_query = total_refunded_query.filter(ContributionRefund.processed_at >= start_date)
        if end_date:
            total_refunded_query = total_refunded_query.filter(ContributionRefund.processed_at <= end_date)
        total_refunded = total_refunded_query.scalar() or 0

        if not rows:
            logger.info("Workflow decision: contribution refund report empty | context=%s", context)

        return {
            "header_keys": ["contribution_type", "source", "refund_amount", "reason", "status", "created_at", "created_by"],
            "headers": [
                translate("report_exports.labels.headers.contribution_type", lang),
                translate("report_exports.labels.headers.source", lang),
                translate("report_exports.labels.headers.refund_amount", lang),
                translate("report_exports.labels.headers.reason", lang),
                translate("report_exports.labels.headers.status", lang),
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.created_by", lang),
            ],
            "rows": rows,
            "total_refunded": total_refunded,
        }
