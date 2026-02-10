#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.commands.handlers import onboarding_handler as _shared
from app.commands.handlers.onboarding_handler import *  # noqa: F401,F403


def _sync_shared_dependencies() -> None:
    dependency_names = [
        "JoinCodeService",
        "OnboardingService",
        "OnboardingQueryService",
        "error_response",
        "join_lines",
        "success_response",
        "parse_target_phone",
        "get_latest_event",
    ]
    for name in dependency_names:
        setattr(_shared, name, globals()[name])


def handle_onboarding_intent(*, db, intent, phone_number, message, member):
    _sync_shared_dependencies()
    return _shared.handle_onboarding_intent(
        db=db,
        intent=intent,
        phone_number=phone_number,
        message=message,
        member=member,
    )
