#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.commands.handlers import public_handler as _shared
from app.commands.handlers.public_handler import *  # noqa: F401,F403


def _sync_shared_dependencies() -> None:
    dependency_names = [
        "FoodPassService",
        "PaymentService",
        "RefundService",
        "PaymentRequestService",
        "RefundRequestService",
        "BlockContributionReport",
        "PublicEventSummaryReport",
        "AuditLog",
        "Payment",
        "UserQueryService",
        "logger",
        "error_response",
        "format_currency",
        "format_heading",
        "join_lines",
        "success_response",
        "parse_amount",
        "parse_pass_counts",
        "parse_reason",
        "parse_target_flat",
        "resolve_flat",
    ]
    for name in dependency_names:
        setattr(_shared, name, globals()[name])


def handle_public_intent(*, db, intent, phone_number, message, event, member):
    _sync_shared_dependencies()
    return _shared.handle_public_intent(
        db=db,
        intent=intent,
        phone_number=phone_number,
        message=message,
        event=event,
        member=member,
    )
