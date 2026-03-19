#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.handlers.shared.committee import handle_committee_intent
from app.handlers.shared.common import get_latest_event
from app.handlers.shared.onboarding import handle_onboarding_intent
from app.handlers.shared.public import handle_public_intent
from app.whatsapp.router import detect_whatsapp_intent
from app.db.session import SessionLocal
from app.utils.guards import ensure_committee_member


def handle_message(phone_number: str, message: str):
    inbound_message = InboundMessage(
        channel="whatsapp",
        sender_id=phone_number,
        display_name=phone_number,
        text=message,
        metadata={},
    )
    return handle_inbound_message(
        inbound_message,
        session_factory=SessionLocal,
        committee_member_resolver=ensure_committee_member,
        latest_event_getter=get_latest_event,
        intent_detector=detect_whatsapp_intent,
        onboarding_intent_handler=handle_onboarding_intent,
        committee_intent_handler=handle_committee_intent,
        public_intent_handler=handle_public_intent,
    )
