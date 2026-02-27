#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.handlers.shared import onboarding as _shared

# Backward-compatible explicit re-exports for tests/patching call-sites.
JoinCodeService = _shared.JoinCodeService
OnboardingService = _shared.OnboardingService
OnboardingQueryService = _shared.OnboardingQueryService
_ORIGINAL_GET_LATEST_EVENT = _shared.get_latest_event
_ORIGINAL_RESOLVE_SENDER_SOCIETY_ID = _shared.resolve_sender_society_id

get_latest_event = _ORIGINAL_GET_LATEST_EVENT
resolve_sender_society_id = _ORIGINAL_RESOLVE_SENDER_SOCIETY_ID


def handle_onboarding_intent(*, db, intent, phone_number, message, member):
    original_get_latest_event = _shared.get_latest_event
    original_resolve_sender_society_id = _shared.resolve_sender_society_id
    if get_latest_event is not _ORIGINAL_GET_LATEST_EVENT:
        _shared.get_latest_event = get_latest_event
    if resolve_sender_society_id is not _ORIGINAL_RESOLVE_SENDER_SOCIETY_ID:
        _shared.resolve_sender_society_id = resolve_sender_society_id
    try:
        return _shared.handle_onboarding_intent(
            db=db,
            intent=intent,
            phone_number=phone_number,
            message=message,
            member=member,
        )
    finally:
        _shared.get_latest_event = original_get_latest_event
        _shared.resolve_sender_society_id = original_resolve_sender_society_id


__all__ = ["handle_onboarding_intent"]
