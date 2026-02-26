"""WhatsApp approval list flow helpers."""

from app.modules.onboarding.admin_query_service import AdminOnboardingQueryService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.whatsapp.response_templates import format_currency
from app.utils.logger import logger

from app.commands.handlers.common import get_latest_event, get_latest_event_for_society
from app.utils.guards import ensure_committee_member

WHATSAPP_APPROVAL_ROW_LIMIT = 10


def _is_committee_member(*, db, sender_id: str, external_user_id: str) -> bool:
    try:
        ensure_committee_member(
            sender_id,
            db,
            channel_type="whatsapp",
            external_user_id=external_user_id,
        )
        return True
    except Exception:
        return False


def _get_committee_member(*, db, sender_id: str, external_user_id: str):
    try:
        return ensure_committee_member(
            sender_id,
            db,
            channel_type="whatsapp",
            external_user_id=external_user_id,
        )
    except Exception:
        return None


def _get_latest_event_in_context(*, db, society_id):
    event = get_latest_event_for_society(db, society_id)
    if event:
        return event
    return get_latest_event(db)

def _send_approval_selection_list(
    *,
    client,
    sender_id: str,
    approval_type: str,
    db,
    canonical_sender: str,
    external_user_id: str,
) -> bool:
    if not _is_committee_member(
        db=db,
        sender_id=canonical_sender,
        external_user_id=external_user_id,
    ):
        client.send_text_message(sender_id, "Access restricted.")
        return True

    committee_member = _get_committee_member(db=db, sender_id=canonical_sender, external_user_id=external_user_id)
    society_id = getattr(committee_member, "society_id", None)
    latest_event = _get_latest_event_in_context(db=db, society_id=society_id)
    if not latest_event:
        client.send_text_message(sender_id, "No active event found.")
        return True

    if approval_type == "user":
        pending_users = AdminOnboardingQueryService.list_pending_users(
            db=db,
            society_id=latest_event.society_id,
        )
        rows = [
            {
                "id": f"approve user {pending.request_code}",
                "title": pending.request_code[:24],
                "description": f"Flat {flat.flat_number}"[:72],
            }
            for pending, flat in pending_users[:WHATSAPP_APPROVAL_ROW_LIMIT]
        ]
        empty_message = "No pending user requests."
        fallback_template = "approve user REQ-001"
        header_text = "Approve User"

    elif approval_type == "payment":
        pending_payments = PaymentRequestService.list_requests(
            db=db,
            event_id=latest_event.id,
            status="requested",
        )
        rows = [
            {
                "id": f"approve payment {request.request_code}",
                "title": request.request_code[:24],
                "description": (
                    f"{flat.flat_number} · {format_currency(request.amount)}"
                )[:72],
            }
            for request, flat in pending_payments[:WHATSAPP_APPROVAL_ROW_LIMIT]
        ]
        empty_message = "No pending payment requests."
        fallback_template = "approve payment PAY-001"
        header_text = "Approve Payment"

    else:
        pending_refunds = RefundRequestService.list_requests(
            db=db,
            event_id=latest_event.id,
            status="requested",
        )
        rows = [
            {
                "id": f"approve refund {request.request_code}",
                "title": request.request_code[:24],
                "description": (
                    f"{flat.flat_number} · {format_currency(request.amount)}"
                )[:72],
            }
            for request, flat in pending_refunds[:WHATSAPP_APPROVAL_ROW_LIMIT]
        ]
        empty_message = "No pending refund requests."
        fallback_template = "approve refund REF-001"
        header_text = "Approve Refund"

    if not rows:
        client.send_text_message(sender_id, empty_message)
        return True

    try:
        client.send_list_message(
            to_phone=sender_id,
            header_text=header_text,
            body_text="Select a request to approve",
            button_text="Approve",
            sections=[{"title": "Pending Requests", "rows": rows}],
            footer_text="If list selection is unavailable, use the command template below.",
        )
    except Exception:
        logger.exception("Failed to send approval selection list", extra={"approval_type": approval_type})
        client.send_text_message(sender_id, fallback_template)
    return True
