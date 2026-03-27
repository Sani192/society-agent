#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:35:03 2026

@author: anonymous
"""

# app/whatsapp/handlers/onboarding_handler.py

from app.modules.onboarding.join_code_service import JoinCodeService
from app.modules.onboarding.onboarding_service import OnboardingService
from app.modules.onboarding.onboarding_query_service import OnboardingQueryService
from app.whatsapp.response_templates import (
    error_response,
    join_lines,
    success_response,
)
from app.commands.parser import parse_target_phone
from app.handlers.shared.common import get_latest_event, resolve_sender_society_id
from app.i18n.catalog import translate


def handle_onboarding_intent(
    *,
    db,
    intent,
    phone_number,
    message,
    member,
    lang: str | None = None,
):
    if intent == "JOIN":
        parts = message.split()
        if len(parts) < 3:
            return error_response(translate("onboarding.join.example", lang))

        join_code = parts[1]
        flat_number = parts[2]

        target_phone = None
        if member:
            target_phone = parse_target_phone(message)
            if not target_phone and len(parts) >= 4:
                target_phone = parts[3]

        society = JoinCodeService.get_society_by_join_code(db, join_code)
        if not society:
            return error_response(translate("onboarding.join.invalid_code", lang))

        try:
            result = OnboardingService.start_onboarding(
                db=db,
                society=society,
                user_identifier=target_phone or phone_number,
                flat_number=flat_number
            )
        except Exception as exc:
            return error_response(str(exc))

        if result == "APPROVED":
            return success_response(translate("onboarding.join.approved", lang))

        return success_response(
            join_lines([
                translate("onboarding.join.request_sent", lang),
                f"Request ID: *{result}*",
                translate("onboarding.join.notify_after_approval", lang),
            ]),
            heading=translate("onboarding.join.request_submitted_heading", lang),
            emoji="⏳"
        )

    if intent == "JOIN_STATUS":
        society_id = getattr(member, "society_id", None) or resolve_sender_society_id(db, phone_number)
        if not society_id:
            latest_event = get_latest_event(db)
            society_id = getattr(latest_event, "society_id", None)
        if not society_id:
            return error_response(translate("onboarding.join_status.no_society_context", lang))


        target_phone = None
        if member:
            target_phone = parse_target_phone(message)
            if not target_phone:
                parts = message.split()
                if len(parts) >= 3:
                    target_phone = parts[2]

        status = OnboardingQueryService.get_user_join_status(
            db=db,
            society_id=society_id,
            user_identifier=target_phone or phone_number
        )

        if status == "APPROVED":
            return success_response(translate("onboarding.join_status.approved", lang))

        if status == "PENDING":
            return success_response(
                translate("onboarding.join_status.pending", lang),
                heading=translate("onboarding.join_status.pending_heading", lang),
                emoji="⏳"
            )

        return error_response(translate("onboarding.join_status.not_found", lang))

    return None
