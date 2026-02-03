#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:33 2026

@author: anonymous
"""

# app/whatsapp/handler.py

from app.db.session import SessionLocal
from app.utils.response import error
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.whatsapp.router import detect_intent
from app.whatsapp.handlers.common import get_latest_event
from app.whatsapp.handlers.public_handler import handle_public_intent
from app.whatsapp.handlers.committee_handler import handle_committee_intent
from app.whatsapp.handlers.onboarding_handler import handle_onboarding_intent

def handle_message(phone_number: str, message: str):
    logger.info(f"Incoming message from {phone_number}: {message}")
    db = SessionLocal()

    member = None
    try:
        member = ensure_committee_member(phone_number, db)
    except Exception as e:
        logger.info("Not a committee member – allowed for member-level commands")
        pass

# =============================================================================
#     try:
#         ensure_admin(phone_number)
#     except Exception as e:
#         logger.exception("Unhandled error in WhatsApp handler")
#         return error("Something went wrong. Please contact admin.")
# =============================================================================


    event = get_latest_event(db)

    intent = detect_intent(message)
    if not intent:
        return "❓ Sorry, I didn’t understand this command."

    try:
        onboarding_response = handle_onboarding_intent(
            db=db,
            intent=intent,
            phone_number=phone_number,
            message=message,
            member=member
        )
        if onboarding_response:
            return onboarding_response

        if member:
            committee_response = handle_committee_intent(
                db=db,
                intent=intent,
                message=message,
                event=event,
                member=member
            )
            if committee_response:
                return committee_response

        public_response = handle_public_intent(
            db=db,
            intent=intent,
            phone_number=phone_number,
            message=message,
            event=event,
            member=member
        )
        if public_response:
            return public_response

        return error("Command not supported.")


    except Exception as e:
        return error(str(e))

    finally:
        db.close()
