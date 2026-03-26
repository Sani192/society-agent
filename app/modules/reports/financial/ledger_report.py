#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 17:23:45 2026

@author: anonymous
"""

import logging
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from app.i18n.catalog import translate

from app.db.models import (
    Payment,
    Refund,
    EventExpense,
    EventContribution,
    ContributionRefund,
    SocietyBalance,
    Flat,
    CommitteeMember
)
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class LedgerReport:

    @staticmethod
    @log_service_call(logger, "LedgerReport.generate")
    def generate(db: Session, *, event_id, society_id, lang: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None):
        context = build_log_context(event_id=event_id, society_id=society_id)
        ledger: list[list[Any]] = []
        running_total = 0
        system_label = translate("report_exports.labels.system", lang)
        not_available = translate("report_exports.labels.not_available", lang)

        opening = (
            db.query(SocietyBalance.opening_balance)
            .filter(
                SocietyBalance.event_id == event_id,
                SocietyBalance.society_id == society_id
            )
            .scalar()
        ) or 0

        ledger.append([translate("report_exports.labels.rows.opening_balance", lang), not_available, opening, not_available, system_label])

        payments_query = (
            db.query(Flat.flat_number, Payment.paid_amount, Payment.paid_at)
            .join(Flat, Flat.id == Payment.flat_id)
            .filter(Payment.event_id == event_id)
        )
        if start_date:
            payments_query = payments_query.filter(Payment.paid_at >= start_date)
        if end_date:
            payments_query = payments_query.filter(Payment.paid_at <= end_date)

        for flat, amount, paid_at in payments_query.all():
            ledger.append([
                translate("report_exports.labels.rows.member_payment", lang),
                translate("report_exports.labels.flat_prefix", lang, flat=flat),
                amount,
                format_timestamp(paid_at),
                system_label,
            ])
            running_total += int(amount or 0)

        sponsors_query = (
            db.query(EventContribution.source_name, EventContribution.amount, EventContribution.created_at)
            .filter(EventContribution.event_id == event_id, EventContribution.amount.isnot(None))
        )
        if start_date:
            sponsors_query = sponsors_query.filter(EventContribution.created_at >= start_date)
        if end_date:
            sponsors_query = sponsors_query.filter(EventContribution.created_at <= end_date)

        for name, amount, created_at in sponsors_query.all():
            ledger.append([translate("report_exports.labels.rows.sponsor_contribution", lang), name, amount, format_timestamp(created_at), system_label])
            running_total += int(amount or 0)

        refunds_query = (
            db.query(Flat.flat_number, Refund.amount, Refund.created_at, CommitteeMember.name)
            .join(Flat, Flat.id == Refund.flat_id)
            .outerjoin(CommitteeMember, CommitteeMember.id == Refund.created_by)
            .filter(Refund.event_id == event_id, Refund.status.in_(["approved", "refunded"]))
        )
        if start_date:
            refunds_query = refunds_query.filter(Refund.created_at >= start_date)
        if end_date:
            refunds_query = refunds_query.filter(Refund.created_at <= end_date)

        for flat, amount, created_at, created_by in refunds_query.all():
            ledger.append([
                translate("report_exports.labels.rows.member_refund", lang),
                translate("report_exports.labels.flat_prefix", lang, flat=flat),
                -amount,
                format_timestamp(created_at),
                created_by or system_label,
            ])
            running_total -= int(amount or 0)

        sponsor_refunds_query = (
            db.query(EventContribution.source_name, ContributionRefund.amount, ContributionRefund.processed_at)
            .join(ContributionRefund, ContributionRefund.contribution_id == EventContribution.id)
            .filter(EventContribution.event_id == event_id)
        )
        if start_date:
            sponsor_refunds_query = sponsor_refunds_query.filter(ContributionRefund.processed_at >= start_date)
        if end_date:
            sponsor_refunds_query = sponsor_refunds_query.filter(ContributionRefund.processed_at <= end_date)

        for name, amount, processed_at in sponsor_refunds_query.all():
            ledger.append([translate("report_exports.labels.rows.sponsor_refund", lang), name, -amount, format_timestamp(processed_at), system_label])
            running_total -= int(amount or 0)

        expenses_query = (
            db.query(EventExpense.description, EventExpense.amount, EventExpense.created_at)
            .filter(EventExpense.event_id == event_id)
        )
        if start_date:
            expenses_query = expenses_query.filter(EventExpense.created_at >= start_date)
        if end_date:
            expenses_query = expenses_query.filter(EventExpense.created_at <= end_date)

        for desc, amount, created_at in expenses_query.all():
            ledger.append([translate("report_exports.labels.rows.expense", lang), desc, -amount, format_timestamp(created_at), system_label])
            running_total -= int(amount or 0)

        if len(ledger) <= 1:
            logger.info("Workflow decision: ledger has only opening entries | context=%s", context)

        closing = int(opening) + running_total

        ledger.append([translate("report_exports.labels.rows.closing_balance", lang), not_available, closing, not_available, system_label])
        if len(ledger) <= 2:
            logger.info("Workflow decision: ledger has no transaction rows | context=%s", context)

        return {
            "header_keys": ["type", "reference", "amount", "created_at", "created_by"],
            "headers": [
                translate("report_exports.labels.headers.type", lang),
                translate("report_exports.labels.headers.reference", lang),
                translate("report_exports.labels.headers.amount", lang),
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.created_by", lang),
            ],
            "rows": ledger
        }
