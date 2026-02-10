#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:33 2026

@author: anonymous
"""

# app/whatsapp/handler.py

from app.db.session import SessionLocal
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.whatsapp.handlers.committee_handler import handle_committee_intent
from app.whatsapp.handlers.common import get_latest_event
from app.whatsapp.handlers.onboarding_handler import handle_onboarding_intent
from app.whatsapp.handlers.public_handler import handle_public_intent
from app.whatsapp.response_templates import error_response, info_response
from app.whatsapp.router import detect_intent


def handle_message(phone_number: str, message: str):
    logger.info(
        "Incoming WhatsApp message",
        extra={"phone_number": phone_number, "message_text": message},
    )
    db = SessionLocal()

    try:
        member = None
        try:
            member = ensure_committee_member(phone_number, db)
            logger.info("Sender is committee member", extra={"phone_number": phone_number})
        except Exception:
            logger.info(
                "Sender is not a committee member; continuing with member/public flows",
                extra={"phone_number": phone_number},
            )

        event = get_latest_event(db)
        logger.info("Loaded latest event context", extra={"event_id": getattr(event, 'id', None)})

        intent = detect_intent(message)
        if not intent:
            logger.info("No intent detected for message", extra={"phone_number": phone_number})
            return info_response("Sorry, I didn’t understand this command.")

        logger.info("Intent detected", extra={"intent": intent, "phone_number": phone_number})
        onboarding_response = handle_onboarding_intent(
            db=db,
            intent=intent,
            phone_number=phone_number,
            message=message,
            member=member,
        )
        if onboarding_response:
            logger.info("Handled by onboarding intent handler", extra={"intent": intent})
            return onboarding_response

        if member:
            committee_response = handle_committee_intent(
                db=db,
                intent=intent,
                message=message,
                event=event,
                member=member,
            )
            if committee_response:
                logger.info("Handled by committee intent handler", extra={"intent": intent})
                return committee_response

        public_response = handle_public_intent(
            db=db,
            intent=intent,
            phone_number=phone_number,
            message=message,
            event=event,
            member=member,
        )
        if public_response:
            logger.info("Handled by public intent handler", extra={"intent": intent})
            return public_response

        logger.warning("Intent reached unsupported fallback", extra={"intent": intent})
        return error_response("Command not supported.")

    except Exception:
        logger.exception("Unhandled error in WhatsApp handler")
        return error_response("Something went wrong. Please try again later.")
    finally:
        logger.info("Closing WhatsApp handler DB session")
        db.close()
