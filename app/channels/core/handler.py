from __future__ import annotations

from collections.abc import Callable

from app.channels.core.types import InboundMessage
from app.commands.handlers.committee_handler import handle_committee_intent
from app.commands.handlers.common import get_latest_event
from app.commands.handlers.onboarding_handler import handle_onboarding_intent
from app.commands.handlers.public_handler import handle_public_intent
from app.commands.router import detect_intent
from app.db.session import SessionLocal
from app.modules.users.channel_identity_service import (
    link_member_by_code,
    link_member_by_phone,
)
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.whatsapp.event_creation_session import (
    build_event_creation_session_key,
    get_event_creation_session,
)
from app.whatsapp.committee_action_session import (
    build_committee_action_session_key,
    get_committee_action_session,
)
from app.whatsapp.response_templates import (
    error_response,
    info_response,
    success_response,
)


def _get_canonical_sender(message: InboundMessage) -> str:
    return message.metadata.get("canonical_sender_id") or message.sender_id


def _attempt_telegram_member_link(
    *, db, message: InboundMessage, intent: str | None
) -> str | None:
    if message.channel != "telegram" or not intent:
        return None

    if intent == "LINK_MEMBER":
        parts = message.text.split()
        if len(parts) < 3:
            return info_response("Use: link member CODE")

        code = parts[2]
        linked_member = link_member_by_code(
            db=db,
            channel_type="telegram",
            sender_id=message.sender_id,
            code=code,
            username=message.metadata.get("username"),
        )
        if not linked_member:
            return error_response("Invalid or expired link code.")
        return success_response("Telegram account linked successfully.")

    if intent == "VERIFY_PHONE":
        parts = message.text.split()
        if len(parts) < 3:
            return info_response("Use: verify phone <number>")

        phone = parts[2]
        linked_member = link_member_by_phone(
            db=db,
            channel_type="telegram",
            sender_id=message.sender_id,
            phone_number=phone,
            username=message.metadata.get("username"),
        )
        if not linked_member:
            return error_response("Phone verification failed. Contact committee.")
        return success_response("Phone verified. Telegram account linked.")

    return None


def handle_inbound_message(
    message: InboundMessage,
    *,
    session_factory: Callable[[], object] = SessionLocal,
    committee_member_resolver: Callable[..., object] = ensure_committee_member,
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
        canonical_sender_id = _get_canonical_sender(message)
        member = None
        try:
            try:
                member = committee_member_resolver(
                    canonical_sender_id,
                    db,
                    channel_type=message.channel,
                    external_user_id=message.sender_id,
                    username=message.metadata.get("username"),
                )
            except TypeError:
                member = committee_member_resolver(canonical_sender_id, db)
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
        logger.info(
            "Loaded latest event context",
            extra={"event_id": getattr(event, "id", None)},
        )

        intent = intent_detector(message.text)

        if not intent and member and message.channel == "whatsapp":
            event_session_key = build_event_creation_session_key(
                member_id=str(getattr(member, "id", "")),
                sender_id=canonical_sender_id,
            )
            if get_event_creation_session(event_session_key):
                intent = "ADD_EVENT"

        if not intent and member and message.channel == "whatsapp":
            committee_session_key = build_committee_action_session_key(
                member_id=str(getattr(member, "id", "")),
                sender_id=canonical_sender_id,
            )
            if get_committee_action_session(committee_session_key):
                intent = "COMMITTEE_PENDING_ACTION"

        link_response = _attempt_telegram_member_link(
            db=db, message=message, intent=intent
        )
        if link_response:
            return link_response

        if not intent:
            logger.info(
                "No intent detected",
                extra={"sender_id": message.sender_id, "channel": message.channel},
            )
            if message.channel == "telegram" and not member:
                return info_response(
                    "I couldn't detect a command. If you're a committee member, use 'link member <code>' or 'verify phone <number>' to onboard Telegram."
                )
            if message.channel == "whatsapp":
                return info_response(
                    "Command not supported. Please use *commands* to view available commands."
                )
            return info_response("Sorry, I didn’t understand this command.")

        onboarding_response = onboarding_intent_handler(
            db=db,
            intent=intent,
            phone_number=canonical_sender_id,
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
                inbound_message=message,
            )
            if committee_response:
                return committee_response

        public_response = public_intent_handler(
            db=db,
            intent=intent,
            phone_number=canonical_sender_id,
            message=message.text,
            event=event,
            member=member,
        )
        if public_response:
            return public_response

        logger.warning(
            "Intent reached unsupported fallback",
            extra={"intent": intent, "channel": message.channel, "sender_id": message.sender_id},
        )
        if message.channel == "whatsapp":
            return info_response(
                "Command not supported. Please use *commands* to view available commands."
            )
        return error_response("Command not supported.")

    except Exception:
        logger.exception("Unhandled error in shared channel handler")
        return error_response("Something went wrong. Please try again later.")
    finally:
        db.close()
