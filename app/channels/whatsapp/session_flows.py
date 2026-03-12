"""Session-driven conversational flows for WhatsApp."""

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.commands.parser import parse_pass_counts
from app.db.models import Event
from app.db.session import SessionLocal
from app.modules.onboarding.join_code_service import JoinCodeService
from app.whatsapp.finance_action_session import (
    FinanceActionSessionState,
    build_finance_action_session_key,
    clear_finance_action_session,
    get_finance_action_session,
    save_finance_action_session,
)
from app.whatsapp.join_session import (
    JoinSessionState,
    build_join_session_key,
    clear_join_session,
    get_join_session,
    save_join_session,
)

FINANCE_EVENT_ACTIONS = {"VIEW_BALANCE", "MAKE_PAYMENT"}
WHATSAPP_FINANCE_EVENT_ROW_PREFIX = "finance-event::"


def _parse_finance_event_selection(message_text: str) -> str | None:
    text = (message_text or "").strip().lower()
    if not text.startswith(WHATSAPP_FINANCE_EVENT_ROW_PREFIX):
        return None
    return text[len(WHATSAPP_FINANCE_EVENT_ROW_PREFIX):].strip() or None


def handle_session_flow(*, client, message) -> bool:
    join_session_key = build_join_session_key(sender_id=message.sender_id)
    join_session = get_join_session(join_session_key)
    if join_session and join_session.pending_action == "JOIN":
        user_text = message.text.strip()
        db = SessionLocal()
        try:
            if not join_session.join_code:
                society = JoinCodeService.get_society_by_join_code(db, user_text)
                if not society:
                    client.send_text_message(message.sender_id, "❌ Invalid join code.")
                    return True
                save_join_session(
                    join_session_key,
                    JoinSessionState(pending_action="JOIN", join_code=user_text),
                )
                client.send_text_message(message.sender_id, "Please enter flat number")
                return True

            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            synthetic_command = f"join {join_session.join_code} {user_text}"
            reply_text = handle_inbound_message(
                InboundMessage(
                    channel=message.channel,
                    sender_id=message.sender_id,
                    display_name=message.display_name,
                    text=synthetic_command,
                    metadata={**message.metadata, "canonical_sender_id": canonical_sender},
                )
            )
            clear_join_session(join_session_key)
            client.send_text_message(message.sender_id, reply_text)
            return True
        finally:
            db.close()

    finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
    finance_session = get_finance_action_session(finance_session_key)
    normalized_text = (message.text or "").strip().lower()
    selected_finance_event_id = _parse_finance_event_selection(message.text)

    if finance_session and selected_finance_event_id and finance_session.pending_action in FINANCE_EVENT_ACTIONS:
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            selected_event = db.query(Event).filter(Event.id == selected_finance_event_id).first()
            if not selected_event:
                client.send_text_message(message.sender_id, "Invalid event selection. Please try again.")
                return True
            save_finance_action_session(
                finance_session_key,
                FinanceActionSessionState(
                    pending_action=finance_session.pending_action,
                    event_id=str(selected_event.id),
                ),
            )
            synthetic_ui_message = InboundMessage(
                channel=message.channel,
                sender_id=message.sender_id,
                display_name=message.display_name,
                text=("ui::finance:view-balance" if finance_session.pending_action == "VIEW_BALANCE" else "ui::make-payment"),
                metadata={**message.metadata, "canonical_sender_id": canonical_sender},
            )
            from app.channels.whatsapp.ui_router import _try_handle_ui_message

            _try_handle_ui_message(client=client, message=synthetic_ui_message)
            return True
        finally:
            db.close()

    if finance_session and normalized_text == "cancel":
        clear_finance_action_session(finance_session_key)
        client.send_text_message(message.sender_id, "Cancelled. You can use menu to start again.")
        return True

    if finance_session and finance_session.pending_action == "PAY_CUSTOM" and normalized_text.isdigit():
        reply_text = handle_inbound_message(
            InboundMessage(
                channel=message.channel,
                sender_id=message.sender_id,
                display_name=message.display_name,
                text=f"pay {normalized_text}",
                metadata=message.metadata,
            )
        )
        clear_finance_action_session(finance_session_key)
        client.send_text_message(message.sender_id, reply_text)
        return True

    if finance_session and finance_session.pending_action == "REFUND_REQUEST" and normalized_text:
        reply_text = handle_inbound_message(
            InboundMessage(
                channel=message.channel,
                sender_id=message.sender_id,
                display_name=message.display_name,
                text=f"refund {message.text.strip()}",
                metadata=message.metadata,
            )
        )
        clear_finance_action_session(finance_session_key)
        client.send_text_message(message.sender_id, reply_text)
        return True

    if finance_session and finance_session.pending_action == "ADD_PASS_COUNTS" and normalized_text:
        counts = parse_pass_counts(normalized_text)
        if sum(counts.values()) == 0:
            client.send_text_message(message.sender_id, "❌ Specify counts. Example: veg 2 jain 1 kids 1")
            return True

        synthetic_command = f"add pass veg {counts['veg']} jain {counts['jain']} kids {counts['kids']}"
        reply_text = handle_inbound_message(
            InboundMessage(
                channel=message.channel,
                sender_id=message.sender_id,
                display_name=message.display_name,
                text=synthetic_command,
                metadata=message.metadata,
            )
        )
        if reply_text.startswith("✅"):
            clear_finance_action_session(finance_session_key)
        client.send_text_message(message.sender_id, reply_text)
        return True

    return False
