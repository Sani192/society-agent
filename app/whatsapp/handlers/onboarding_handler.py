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
from app.utils.response import success, error
from app.whatsapp.parser import parse_target_phone
from app.whatsapp.handlers.common import get_latest_event


def handle_onboarding_intent(
    *,
    db,
    intent,
    phone_number,
    message,
    member
):
    if intent == "JOIN":
        parts = message.split()
        if len(parts) < 3:
            return error("Example: join ABC123 A-101")

        join_code = parts[1]
        flat_number = parts[2]

        target_phone = None
        if member:
            target_phone = parse_target_phone(message)
            if not target_phone and len(parts) >= 4:
                target_phone = parts[3]

        society = JoinCodeService.get_society_by_join_code(db, join_code)
        if not society:
            return error("Invalid join code.")

        try:
            result = OnboardingService.start_onboarding(
                db=db,
                society=society,
                user_identifier=target_phone or phone_number,
                flat_number=flat_number
            )
        except Exception as exc:
            return error(str(exc))

        if result == "APPROVED":
            return success("✅ You are successfully added to the society.")

        return success(
            "⏳ Your request is sent for approval.\n"
            f"Request ID: *{result}*\n"
            "You will be notified once approved."
        )

    if intent == "JOIN_STATUS":
        latest_event = get_latest_event(db)
        if not latest_event:
            return error("No society context found.")

        society_id = latest_event.society_id

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
            return success("✅ Your membership is approved.")

        if status == "PENDING":
            return success("⏳ Your join request is pending approval.")

        return error("You have not requested to join any society.")

    return None
