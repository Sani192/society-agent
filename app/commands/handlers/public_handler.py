#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.handlers.shared import public as _shared

# Backward-compatible explicit re-exports for tests/patching call-sites.
FoodPassService = _shared.FoodPassService
PaymentService = _shared.PaymentService
RefundService = _shared.RefundService
PaymentRequestService = _shared.PaymentRequestService
RefundRequestService = _shared.RefundRequestService
BlockContributionReport = _shared.BlockContributionReport
PublicEventSummaryReport = _shared.PublicEventSummaryReport
_ORIGINAL_RESOLVE_FLAT = _shared.resolve_flat
resolve_flat = _ORIGINAL_RESOLVE_FLAT


def handle_public_intent(*, db, intent, phone_number, message, event, member):
    original_resolve_flat = _shared.resolve_flat
    if resolve_flat is not _ORIGINAL_RESOLVE_FLAT:
        _shared.resolve_flat = resolve_flat
    try:
        return _shared.handle_public_intent(
            db=db,
            intent=intent,
            phone_number=phone_number,
            message=message,
            event=event,
            member=member,
        )
    finally:
        _shared.resolve_flat = original_resolve_flat


__all__ = ["handle_public_intent"]
