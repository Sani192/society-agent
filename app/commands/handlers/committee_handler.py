#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.handlers.shared import committee as _shared

# Backward-compatible explicit re-exports for tests/patching call-sites.
WhatsAppReportExportService = _shared.WhatsAppReportExportService
EventService = _shared.EventService
ContributionService = _shared.ContributionService
ContributionRefundService = _shared.ContributionRefundService
ExpenseService = _shared.ExpenseService
PaymentRequestService = _shared.PaymentRequestService
RefundRequestService = _shared.RefundRequestService
AdminApprovalService = _shared.AdminApprovalService
AdminOnboardingQueryService = _shared.AdminOnboardingQueryService
PendingPaymentReport = _shared.PendingPaymentReport
EventParticipationReport = _shared.EventParticipationReport

_ORIGINAL_EVENT_STATE_FOR_INTENT = _shared._event_state_for_intent
_ORIGINAL_GET_WHATSAPP_CLIENT = _shared.get_whatsapp_client

_event_state_for_intent = _ORIGINAL_EVENT_STATE_FOR_INTENT
get_whatsapp_client = _ORIGINAL_GET_WHATSAPP_CLIENT


def handle_committee_intent(*, db, intent, message, event, member, inbound_message=None):
    original_event_state = _shared._event_state_for_intent
    original_whatsapp_client = _shared.get_whatsapp_client
    if _event_state_for_intent is not _ORIGINAL_EVENT_STATE_FOR_INTENT:
        _shared._event_state_for_intent = _event_state_for_intent
    if get_whatsapp_client is not _ORIGINAL_GET_WHATSAPP_CLIENT:
        _shared.get_whatsapp_client = get_whatsapp_client
    try:
        return _shared.handle_committee_intent(
            db=db,
            intent=intent,
            message=message,
            event=event,
            member=member,
            inbound_message=inbound_message,
        )
    finally:
        _shared._event_state_for_intent = original_event_state
        _shared.get_whatsapp_client = original_whatsapp_client


__all__ = ["handle_committee_intent"]
