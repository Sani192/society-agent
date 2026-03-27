from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.channels.core.audit_security import redact_text
from app.channels.core.types import InboundMessage
from app.handlers.shared.committee import handle_committee_intent
from app.handlers.shared.common import get_latest_event_for_society, resolve_sender_society_id
from app.handlers.shared.onboarding import handle_onboarding_intent
from app.handlers.shared.public import handle_public_intent
from app.commands.router import detect_intent
from app.db.session import SessionLocal
from app.db.models import Event, MemberIdentity
from app.modules.users.language_service import resolve_sender_language
from app.modules.users.channel_identity_service import (
    link_member_by_code,
    link_member_by_phone,
)
from app.utils.guards import ensure_committee_member
from app.permissions.command_policy import get_event_state, get_intent_state_warning
from app.utils.logger import logger
from app.utils.identity import normalize_identifier
from app.whatsapp.event_creation_session import (
    build_event_creation_session_key,
    get_event_creation_session,
)
from app.whatsapp.committee_action_session import (
    build_committee_action_session_key,
    get_committee_action_session,
)
from app.whatsapp.export_session import (
    build_export_session_key,
    clear_export_session,
    get_export_session,
)
from app.whatsapp.response_templates import (
    build_invalid_command_response,
    error_response,
    info_response,
    success_response,
    INVALID_INPUT_METADATA_KEY,
)


def _invalid_command_reply(*, message: InboundMessage, reason: str, is_committee: bool, lang: str | None = None) -> str:
    ctas = None
    if message.channel == "whatsapp" and is_committee:
        ctas = [{"id": "menu"}, {"id": "help"}, {"id": "report options"}]

    reply, contract = build_invalid_command_response(channel=message.channel, reason=reason, ctas=ctas, lang=lang)
    message.metadata[INVALID_INPUT_METADATA_KEY] = {
        "response_type": contract.response_type,
        "severity": contract.severity,
        "reason": contract.reason,
        "ctas": list(contract.ctas),
    }
    return reply



REPORT_INTENTS_REQUIRING_EVENT_CONTEXT = {
    "SUMMARY",
    "BLOCK_REPORT",
    "PARTICIPATION_REPORT",
}


LEGACY_REPORT_GUIDANCE = {
    "LEGACY_REPORTS_ALIAS": "`reports` is no longer supported. Send `report options` to view exportable reports.",
    "LEGACY_REPORT_EXPORT": "`report export ...` is no longer supported. Send `report options`, then reply with `export <number>` or tap an `export::<key>` option.",
}

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
    trace_id: str | None = None,
    correlation_id: str | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    committee_member_resolver: Callable[..., object] = ensure_committee_member,
    latest_event_getter: Callable[..., Any] = get_latest_event_for_society,
    intent_detector: Callable[..., str | None] = detect_intent,
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
            "message_text": redact_text(message.text),
            "trace_id": trace_id,
            "correlation_id": correlation_id,
        },
    )
    db = session_factory()

    def _persist_member_inbound_activity() -> None:
        if message.channel != "whatsapp":
            return

        sender_candidates = {
            message.sender_id,
            message.metadata.get("canonical_sender_id"),
            normalize_identifier(message.sender_id),
            normalize_identifier(message.metadata.get("canonical_sender_id", "")),
        }
        sender_candidates = {candidate for candidate in sender_candidates if candidate}
        if not sender_candidates:
            return

        identity = (
            db.query(MemberIdentity)
            .filter(
                (MemberIdentity.whatsapp_user_id.in_(tuple(sender_candidates)))
                | (MemberIdentity.normalized_identifier.in_(tuple(sender_candidates)))
                | (MemberIdentity.normalized_phone.in_(tuple(sender_candidates)))
            )
            .first()
        )
        if not identity:
            return

        metadata = dict(identity.metadata_json or {})
        channel_state = dict(metadata.get("channel_state") or {})
        whatsapp_state = dict(channel_state.get("whatsapp") or {})
        whatsapp_state["last_inbound_at"] = message.metadata.get("timestamp_iso")
        whatsapp_state["last_inbound_sender"] = message.sender_id
        whatsapp_state["opt_in"] = True
        channel_state["whatsapp"] = whatsapp_state
        metadata["channel_state"] = channel_state
        setattr(identity, "metadata_json", metadata)
        db.commit()

    try:
        _persist_member_inbound_activity()
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

        lang = resolve_sender_language(
            db,
            sender_id=canonical_sender_id,
            channel=message.channel,
        )

        society_id = getattr(member, "society_id", None)
        if not society_id:
            society_id = resolve_sender_society_id(db, canonical_sender_id)

        try:
            event = latest_event_getter(db, society_id)
        except TypeError:
            event = latest_event_getter(db)
        logger.info(
            "Loaded latest event context",
            extra={
                "event_id": getattr(event, "id", None),
                "society_id": str(society_id) if society_id else None,
            },
        )

        allow_numeric_export_selection = False
        if message.channel == "whatsapp":
            export_session_key = build_export_session_key(
                member_id=str(getattr(member, "id", "")) if member else None,
                sender_id=canonical_sender_id,
            )
            allow_numeric_export_selection = bool(
                export_session_key and get_export_session(export_session_key)
            )

        try:
            intent = intent_detector(
                message.text,
                allow_numeric_export_selection=allow_numeric_export_selection,
            )
        except TypeError:
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

        if intent == "MENU" and message.channel == "whatsapp":
            export_session_key = build_export_session_key(
                member_id=str(getattr(member, "id", "")) if member else None,
                sender_id=canonical_sender_id,
            )
            clear_export_session(export_session_key)

        if message.channel == "whatsapp" and intent in REPORT_INTENTS_REQUIRING_EVENT_CONTEXT:
            export_session_key = build_export_session_key(
                member_id=str(getattr(member, "id", "")) if member else None,
                sender_id=canonical_sender_id,
            )
            report_session = get_export_session(export_session_key)
            selected_event_id = report_session.event_id if report_session else None
            if selected_event_id:
                selected_event_query = db.query(Event).filter(Event.id == selected_event_id)
                if society_id:
                    selected_event_query = selected_event_query.filter(Event.society_id == society_id)
                selected_event = selected_event_query.first()
                if selected_event:
                    event = selected_event

        link_response = _attempt_telegram_member_link(
            db=db, message=message, intent=intent
        )
        if link_response:
            return link_response

        event_state = get_event_state(event)
        blocked_reason = get_intent_state_warning(
            intent=intent,
            event_state=event_state,
            is_committee=bool(member),
        ) if intent else None
        if blocked_reason:
            return info_response(blocked_reason)

        if intent in LEGACY_REPORT_GUIDANCE:
            return info_response(LEGACY_REPORT_GUIDANCE[intent])

        if not intent:
            logger.info(
                "No intent detected",
                extra={"sender_id": message.sender_id, "channel": message.channel},
            )
            if message.channel == "telegram" and not member:
                return _invalid_command_reply(
                    message=message,
                    reason="If you're a committee member, use 'link member <code>' or 'verify phone <number>' to onboard Telegram.",
                    is_committee=False,
                    lang=lang,
                )
            return _invalid_command_reply(
                message=message,
                reason="Try a listed menu command.",
                is_committee=bool(member),
                lang=lang,
            )

        try:
            onboarding_response = onboarding_intent_handler(
                db=db,
                intent=intent,
                phone_number=canonical_sender_id,
                message=message.text,
                member=member,
                lang=lang,
            )
        except TypeError:
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
            try:
                committee_response = committee_intent_handler(
                    db=db,
                    intent=intent,
                    message=message.text,
                    event=event,
                    member=member,
                    inbound_message=message,
                    lang=lang,
                )
            except TypeError:
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

        try:
            public_response = public_intent_handler(
                db=db,
                intent=intent,
                phone_number=canonical_sender_id,
                message=message.text,
                event=event,
                member=member,
                lang=lang,
            )
        except TypeError:
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
        return _invalid_command_reply(
            message=message,
            reason="That command is not available here.",
            is_committee=bool(member),
            lang=lang,
        )

    except Exception:
        logger.exception("Unhandled error in shared channel handler")
        return error_response("Something went wrong. Please try again later.")
    finally:
        db.close()
