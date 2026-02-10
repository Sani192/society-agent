from __future__ import annotations

from collections.abc import Callable

from app.channels.core.types import InboundMessage
from app.commands.handlers.committee_handler import handle_committee_intent
from app.commands.handlers.common import get_latest_event
from app.commands.handlers.onboarding_handler import handle_onboarding_intent
from app.commands.handlers.public_handler import handle_public_intent
from app.commands.router import detect_intent
from app.db.session import SessionLocal
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.whatsapp.response_templates import error_response, info_response


def handle_inbound_message(
    message: InboundMessage,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    committee_member_resolver: Callable[[str, object], object] = ensure_committee_member,
    latest_event_getter: Callable[[object], object] = get_latest_event,
    intent_detector: Callable[[str], str | None] = detect_intent,
    onboarding_intent_handler: Callable[..., str | None] = handle_onboarding_intent,
    committee_intent_handler: Callable[..., str | None] = handle_committee_intent,
    public_intent_handler: Callable[..., str | None] = handle_public_intent,
) -> str:
    logger.info(
        "Incoming channel message",
        extra={
            "channel": message.channel,
            "sender_id": message.sender_id,
            "display_name": message.display_name,
            "message_text": message.text,
        },
    )
    db = session_factory()

    try:
        member = None
        try:
            member = committee_member_resolver(message.sender_id, db)
            logger.info(
                "Sender is committee member",
                extra={"sender_id": message.sender_id, "channel": message.channel},
            )
        except Exception:
            logger.info(
                "Sender is not a committee member; continuing with member/public flows",
                extra={"sender_id": message.sender_id, "channel": message.channel},
            )

        event = latest_event_getter(db)
        logger.info("Loaded latest event context", extra={"event_id": getattr(event, 'id', None)})

        intent = intent_detector(message.text)
        if not intent:
            logger.info("No intent detected", extra={"sender_id": message.sender_id})
            return info_response("Sorry, I didn’t understand this command.")

        onboarding_response = onboarding_intent_handler(
            db=db,
            intent=intent,
            phone_number=message.sender_id,
            message=message.text,
            member=member,
        )
        if onboarding_response:
            return onboarding_response

        if member:
            committee_response = committee_intent_handler(
                db=db,
                intent=intent,
                message=message.text,
                event=event,
                member=member,
            )
            if committee_response:
                return committee_response

        public_response = public_intent_handler(
            db=db,
            intent=intent,
            phone_number=message.sender_id,
            message=message.text,
            event=event,
            member=member,
        )
        if public_response:
            return public_response

        logger.warning("Intent reached unsupported fallback", extra={"intent": intent})
        return error_response("Command not supported.")

    except Exception:
        logger.exception("Unhandled error in shared channel handler")
        return error_response("Something went wrong. Please try again later.")
    finally:
        db.close()
