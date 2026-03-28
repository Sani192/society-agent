#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:33:10 2026

@author: anonymous
"""

# app/whatsapp/handlers/committee_handler.py

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    Flat,
    Payment,
    Refund,
    EventFoodPass,
    WorkflowState,
    AuditLog,
    MemberIdentity,
    UserFlatMapping,
)
from app.modules.expenses.expense_service import ExpenseService
from app.modules.onboarding.admin_approval_service import AdminApprovalService
from app.modules.onboarding.admin_query_service import AdminOnboardingQueryService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.modules.contributions.contribution_service import ContributionService
from app.modules.contributions.contribution_refund_service import (
    ContributionRefundService,
)
from app.modules.reports.pending_payment_report import PendingPaymentReport
from app.modules.reports.event_participation_report import EventParticipationReport
from app.modules.events.service import EventService
from app.modules.events.food_collection_service import FoodCollectionService
from app.modules.committee.committee_member_service import CommitteeMemberService
from app.modules.announcements.manager import AnnouncementManager
from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_exportable_report_options,
)
from app.channels.whatsapp.client import get_whatsapp_client
from app.channels.core.types import InboundMessage
from app.utils.logger import logger
from app.utils.time import utc_now
from app.config import settings
from app.permissions.guard import is_action_allowed
from app.channels.whatsapp.response_templates import (
    error_response,
    format_currency,
    format_datetime,
    format_heading,
    join_lines,
    success_response,
    warning_response,
    info_response,
)
from app.commands.parser import (
    parse_amount,
    parse_event_creation,
    parse_reason,
    parse_target_flat,
)
from app.i18n.catalog import translate


from app.channels.whatsapp.event_creation_session import (
    EventCreationSessionState,
    build_event_creation_session_key,
    clear_event_creation_session,
    get_event_creation_session,
    save_event_creation_session,
)
from app.channels.whatsapp.export_session import (
    ExportSessionState,
    build_export_session_key,
    clear_export_session,
    get_export_session,
    save_export_session,
)
from app.channels.whatsapp.committee_action_session import (
    CommitteeActionSessionState,
    build_committee_action_session_key,
    clear_committee_action_session,
    get_committee_action_session,
    save_committee_action_session,
)




def _parse_add_committee_member_args(message: str) -> tuple[str, str, str] | None:
    raw = (message or "").strip()
    prefix = "add committee member"
    if not raw.lower().startswith(prefix):
        return None
    payload = raw[len(prefix):].strip()
    if not payload:
        return None

    parts = [part.strip() for part in payload.split("|")]
    if len(parts) != 3:
        return None
    name, phone, role = parts
    if not name or not phone or not role:
        return None
    return name, phone, role


def _parse_member_id_and_role(message: str, *, prefix: str) -> tuple[str, str] | None:
    raw = (message or "").strip()
    if not raw.lower().startswith(prefix.lower()):
        return None
    payload = raw[len(prefix):].strip()
    if not payload:
        return None
    parts = payload.split()
    if len(parts) < 2:
        return None
    member_id = parts[0].strip()
    role = parts[1].strip()
    if not member_id or not role:
        return None
    return member_id, role


def _parse_member_id(message: str, *, prefix: str) -> str | None:
    raw = (message or "").strip()
    if not raw.lower().startswith(prefix.lower()):
        return None
    payload = raw[len(prefix):].strip()
    if not payload:
        return None
    return payload.split()[0].strip()


def _parse_token_after_prefix(message: str, *, prefix: str) -> str | None:
    raw = (message or "").strip()
    if not raw.lower().startswith(prefix.lower()):
        return None
    payload = raw[len(prefix):].strip()
    if not payload:
        return None
    return payload.split()[0].strip().upper()


EVENT_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
EVENT_WIZARD_STEPS = [
    "name",
    "event_date",
    "food_types",
    "charge_per_adult",
    "charge_per_child",
    "payment_deadline",
]

INTENT_ROLE_ACTIONS = {
    "ADD_EXPENSE": "ADD_EXPENSE",
    "ADD_SPONSOR": "ADD_SPONSOR",
    "REFUND_SPONSOR": "REFUND",
    "REMIND_FLAT": "PAY",
    "CLOSE_EVENT": "CLOSE_EVENT",
    "ANNOUNCE_EVENT": "ANNOUNCE",
    "ANNOUNCE_SOCIETY": "ANNOUNCE",
}

INTENT_ROLE_WARNINGS = {
    "ADD_EXPENSE": (
        "This action normally requires Secretary approval. "
        "Please ask Chairman to override."
    ),
    "ADD_SPONSOR": "Only Chairman, Secretary, or Treasurer can add sponsor contributions.",
    "REFUND_SPONSOR": "Only Treasurer or Chairman can refund sponsors.",
    "REMIND_FLAT": "This action normally requires Treasurer approval.",
    "CLOSE_EVENT": "Only Chairman, Secretary, or Treasurer can close events.",
    "ANNOUNCE_EVENT": "Only committee members can announce event updates.",
    "ANNOUNCE_SOCIETY": "Only committee members can announce society updates.",
}

CLOSED_OVERRIDE_INTENTS = {"ADD_EXPENSE", "ADD_SPONSOR", "REFUND_SPONSOR"}
COMMITTEE_MEMBER_ROLES = {"chairman", "secretary", "treasurer", "committee_member"}
COMMITTEE_ADMIN_ROLES = {"chairman", "secretary", "treasurer"}
ANNOUNCE_INTENTS = {"ANNOUNCE_EVENT", "ANNOUNCE_SOCIETY"}
ANNOUNCE_MAX_WHATSAPP_TEXT_LENGTH = 1024


def _extract_announcement_body(*, message: str, command_prefix: str) -> str:
    raw_message = message or ""
    left_trimmed_message = raw_message.lstrip()
    if left_trimmed_message.lower().startswith(command_prefix.lower()):
        return left_trimmed_message[len(command_prefix):]
    return ""


def _build_food_counter_open_announcement(*, event_name: str, closes_at) -> str:
    close_time_text = format_datetime(closes_at) if closes_at else None
    lines = [
        f"{event_name}: food counter is now open.",
        "Please keep your token/QR ready for quick serving.",
    ]
    if close_time_text:
        lines.append(f"Counter closes at {close_time_text}.")
    return join_lines(lines)


def _event_wizard_prompt(step: str) -> str:
    prompts = {
        "name": "What is the event name?",
        "event_date": (
            "What is the event date and time?\n"
            f"Use format {EVENT_DATETIME_FORMAT}. Example: 2026-12-31 19:00"
        ),
        "food_types": (
            "Which food types are available?\n"
            "Reply with comma-separated values. Example: veg,jain"
        ),
        "charge_per_adult": "What is the adult charge amount? Example: 300",
        "charge_per_child": "What is the child charge amount? Example: 150",
        "payment_deadline": (
            "Optional: what is the payment deadline?\n"
            f"Use format {EVENT_DATETIME_FORMAT}, or reply `skip`."
        ),
    }
    return prompts[step]


def _extract_override_reason(raw_message: str) -> tuple[str, str | None]:
    if not raw_message:
        return "", None

    marker = " override "
    normalized = f" {raw_message.strip()} "
    if marker not in normalized.lower():
        return raw_message, None

    lower_message = raw_message.lower()
    split_index = lower_message.rfind(" override ")
    base_message = raw_message[:split_index].strip()
    override_reason = raw_message[split_index + len(" override "):].strip() or None
    return base_message, override_reason


def _event_state_for_intent(*, db, event) -> str | None:
    if not event:
        return None

    try:
        state_row = (
            db.query(WorkflowState)
            .filter(WorkflowState.event_id == event.id)
            .first()
        )
    except Exception:
        return None

    if not state_row:
        return None
    return getattr(state_row, "current_state", None)


def can_execute_intent(*, member, intent: str, event_state: str | None, override_reason: str | None) -> tuple[bool, str | None]:
    action = INTENT_ROLE_ACTIONS.get(intent)
    if not action:
        return True, None

    if intent in ANNOUNCE_INTENTS and member.role in COMMITTEE_MEMBER_ROLES:
        return True, None

    if is_action_allowed(member.role, action):
        return True, None

    is_closed_override = (
        intent in CLOSED_OVERRIDE_INTENTS
        and event_state == "CLOSED"
        and member.role in COMMITTEE_MEMBER_ROLES
        and bool((override_reason or "").strip())
    )
    if is_closed_override:
        return True, None

    return False, INTENT_ROLE_WARNINGS.get(intent, "You are not allowed to perform this action.")


def _next_event_wizard_step(current_step: str) -> str | None:
    try:
        idx = EVENT_WIZARD_STEPS.index(current_step)
    except ValueError:
        return None
    if idx + 1 >= len(EVENT_WIZARD_STEPS):
        return None
    return EVENT_WIZARD_STEPS[idx + 1]


def _start_event_creation_wizard(*, session_key: str | None):
    state = EventCreationSessionState(step="name")
    save_event_creation_session(session_key, state)
    return info_response(
        _event_wizard_prompt("name"),
        heading="Event setup (guided)",
        emoji="🧭",
    )


def _handle_event_creation_wizard_step(*, db, member, message: str, session_key: str | None, state: EventCreationSessionState):
    answer = message.strip()

    if state.step == "name":
        if not answer:
            return error_response("Event name cannot be empty. Please enter a valid name.")
        state.name = answer

    elif state.step == "event_date":
        try:
            state.event_date = datetime.strptime(answer, EVENT_DATETIME_FORMAT)
        except ValueError:
            return error_response(
                "Please enter date/time in YYYY-MM-DD HH:MM format. Example: 2026-12-31 19:00"
            )

    elif state.step == "food_types":
        food_types = [item.strip().lower() for item in answer.split(",") if item.strip()]
        if not food_types:
            return info_response("Please provide at least one food type. Example: veg,jain")
        state.food_types = food_types

    elif state.step == "charge_per_adult":
        if not answer.isdigit():
            return info_response("Adult charge must be a whole number. Example: 300")
        state.charge_per_adult = int(answer)

    elif state.step == "charge_per_child":
        if not answer.isdigit():
            return info_response("Child charge must be a whole number. Example: 150")
        state.charge_per_child = int(answer)

    elif state.step == "payment_deadline":
        payment_deadline = None
        if answer.lower() not in {"skip", "none", "na", "n/a"}:
            try:
                payment_deadline = datetime.strptime(answer, EVENT_DATETIME_FORMAT)
            except ValueError:
                return error_response(
                    "Please enter deadline in YYYY-MM-DD HH:MM format, or reply `skip`.\n"
                    "Example: 2026-12-30 18:00"
                )

        created_event = EventService.create_event(
            db=db,
            society_id=member.society_id,
            name=state.name,
            event_date=state.event_date,
            food_types=state.food_types or [],
            charge_per_adult=state.charge_per_adult or 0,
            charge_per_child=state.charge_per_child or 0,
            payment_deadline=payment_deadline,
            created_by=member.id,
        )
        clear_event_creation_session(session_key)

        return success_response(
            join_lines(
                [
                    f"Event: {created_event.name}",
                    f"Date: {format_datetime(created_event.event_date)}",
                    f"Food: {', '.join(created_event.food_types)}",
                    f"Adult: {format_currency(created_event.charge_per_adult)}",
                    f"Child: {format_currency(created_event.charge_per_child)}",
                    f"Deadline: {format_datetime(created_event.payment_deadline)}",
                ]
            ),
            heading="Event created",
            emoji="📅",
        )

    next_step = _next_event_wizard_step(state.step)
    if not next_step:
        clear_event_creation_session(session_key)
        return error_response("Could not continue guided event setup. Please send `add event` to restart.")

    state.step = next_step
    save_event_creation_session(session_key, state)
    return info_response(
        _event_wizard_prompt(next_step),
        heading="Event setup (guided)",
        emoji="🧭",
    )




def _recent_event_options(*, db, society_id):
    cutoff = utc_now() - timedelta(days=365)
    events = (
        db.query(Event)
        .filter(Event.society_id == society_id, Event.event_date >= cutoff)
        .order_by(Event.event_date.desc())
        .all()
    )
    return [
        {
            "id": str(item.id),
            "name": item.name,
            "event_date": format_datetime(item.event_date),
            "status": item.status,
        }
        for item in events
    ]


def _format_report_options_with_event(*, options: list[dict], event_options: list[dict], selected_event_id: str | None) -> str:
    lines = [
        format_heading("Choose report event + report", "📚"),
    ]

    if event_options:
        lines.append("Select event (last 1 year): reply `event <number>`")
        for index, event_option in enumerate(event_options, start=1):
            marker = " ✅" if event_option["id"] == selected_event_id else ""
            lines.append(
                f"{index}. {event_option['name']} ({event_option['event_date']}) [{event_option['status']}]"
                f"{marker}"
            )
    else:
        lines.append("No events found in last 1 year.")

    lines.extend([
        "",
        "Then choose report: reply `export <number>` (or just number).",
    ])

    grouped_options: dict[str, list[tuple[int, dict]]] = {}
    for index, option in enumerate(options, start=1):
        grouped_options.setdefault(option["category"], []).append((index, option))

    for category, entries in grouped_options.items():
        lines.append("")
        lines.append(format_heading(category.title(), "🗂️"))
        for index, option in entries:
            lines.append(f"{index}. {option['label']}")
            lines.append(f"   ↪ Reply: export {index}")
    return join_lines(lines)

def _report_options(*, role: str):
    return list_exportable_report_options(
        registry=build_whatsapp_report_registry(
            handlers_by_code=WhatsAppReportExportService.handlers_by_report_code(),
        ),
        role=role,
    )


def _format_conversational_options(options: list[dict]) -> str:
    lines = [
        format_heading("Choose a report to export", "📚"),
        "Reply with `export <number>` (or just the number) to export as PDF.",
    ]

    grouped_options: dict[str, list[tuple[int, dict]]] = {}
    for index, option in enumerate(options, start=1):
        grouped_options.setdefault(option["category"], []).append((index, option))

    for category, entries in grouped_options.items():
        lines.append("")
        lines.append(format_heading(category.title(), "🗂️"))
        for index, option in entries:
            lines.append(f"{index}. {option['label']}")
            lines.append(f"   ↪ Reply: export {index}")
    return join_lines(lines)


def _dispatch_export_result(*, result, member, inbound_message):
    if result["format"] in {"pdf", "csv", "excel"}:
        target_phone = None
        if inbound_message is not None:
            target_phone = (
                inbound_message.metadata.get("canonical_sender_id")
                or inbound_message.sender_id
            )
        else:
            target_phone = getattr(member, "phone_number", None)

        if not target_phone:
            return error_response("Couldn’t send report right now, try again")

        mime_type_map = {
            "pdf": "application/pdf",
            "csv": "text/csv",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        mime_type = mime_type_map[result["format"]]

        try:
            client = get_whatsapp_client()
            media_id = client.upload_media(
                file_bytes=result["payload"],
                filename=result["filename"],
                mime_type=mime_type,
            )
            client.send_document_message(
                to_phone=target_phone,
                media_id=media_id,
                filename=result["filename"],
                caption=f"{result['category']} {result['report']} ({result['format']})",
            )
        except Exception:
            logger.exception(
                "Failed to deliver exported report via WhatsApp document",
                extra={
                    "target_phone": target_phone,
                    "document_name": result["filename"],
                },
            )
            return error_response("Couldn’t send report right now, try again")

    generated_by = (
        getattr(member, "name", None)
        or getattr(member, "display_name", None)
        or str(getattr(member, "id", "Unknown"))
    )
    event_name = result.get("event_name") or "General"

    response_lines = [
        f"Category: {result['category']}",
        f"Report: {result['report']}",
        f"Format: {result['format']}",
        f"Rows: {result['row_count']}",
        f"Generated by: {generated_by}",
        f"Event Name: {event_name}",
        f"File: {result['filename']}",
    ]
    return success_response(
        join_lines(response_lines),
        heading="Report exported",
        emoji="📤",
    )


def _build_my_tokens_instruction() -> str:
    deep_link = getattr(settings, "WHATSAPP_MY_TOKENS_DEEP_LINK", None)
    if deep_link:
        return f"Open this link to view your tokens: {deep_link}"
    return "Reply with *my tokens* in this chat to view your tokens."


def _notify_generated_food_tokens(*, db, event, generated_tokens, performed_by):
    if not generated_tokens:
        return

    tokens_by_flat: dict = {}
    for token in generated_tokens:
        if not getattr(token, "flat_id", None):
            continue
        tokens_by_flat.setdefault(token.flat_id, []).append(token)

    if not tokens_by_flat:
        return

    flat_rows = (
        db.query(Flat.id, Flat.flat_number)
        .filter(
            Flat.society_id == event.society_id,
            Flat.id.in_(list(tokens_by_flat.keys())),
        )
        .all()
    )
    flat_number_by_id = {flat_id: flat_number for flat_id, flat_number in flat_rows}

    mapping_rows = (
        db.query(
            UserFlatMapping.flat_id,
            MemberIdentity.id,
            MemberIdentity.whatsapp_user_id,
            MemberIdentity.normalized_phone,
        )
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(
            UserFlatMapping.society_id == event.society_id,
            UserFlatMapping.is_active.is_(True),
            UserFlatMapping.flat_id.in_(list(tokens_by_flat.keys())),
        )
        .all()
    )

    recipients_by_flat: dict = {}
    for flat_id, identity_id, whatsapp_user_id, normalized_phone in mapping_rows:
        recipient_phone = whatsapp_user_id or normalized_phone
        if not recipient_phone:
            continue
        recipients = recipients_by_flat.setdefault(flat_id, {})
        recipients[recipient_phone] = identity_id

    instruction = _build_my_tokens_instruction()
    failed_recipients: list[dict] = []
    flat_ids_without_recipients: list[str] = []

    try:
        client = get_whatsapp_client()
    except Exception:
        logger.exception(
            "Failed to initialize WhatsApp client for food token notifications",
            extra={"event_id": str(event.id), "society_id": str(event.society_id)},
        )
        db.add(
            AuditLog(
                society_id=event.society_id,
                entity_type="food_collection",
                entity_id=event.id,
                action="FOOD_TOKEN_NOTIFY_FAILED",
                reason="WhatsApp client unavailable for food token notification",
                performed_by=performed_by,
            )
        )
        return

    for flat_id, flat_tokens in tokens_by_flat.items():
        recipients = recipients_by_flat.get(flat_id) or {}
        if not recipients:
            flat_ids_without_recipients.append(str(flat_id))
            continue

        message_body = join_lines([
            f"🎟️ *{event.name}* tokens are ready.",
            f"Total tokens for your flat: {len(flat_tokens)}",
            instruction,
        ])

        for recipient_phone, identity_id in recipients.items():
            try:
                client.send_text_message(to_phone=recipient_phone, body=message_body)
            except Exception:
                failed_recipients.append(
                    {
                        "flat_id": str(flat_id),
                        "identity_id": str(identity_id),
                        "phone": recipient_phone,
                    }
                )
                logger.exception(
                    "Failed to send food token notification",
                    extra={
                        "event_id": str(event.id),
                        "society_id": str(event.society_id),
                        "flat_id": str(flat_id),
                        "identity_id": str(identity_id),
                        "recipient_phone": recipient_phone,
                    },
                )

    if failed_recipients or flat_ids_without_recipients:
        failure_summary = (
            f"notify_failures={len(failed_recipients)} "
            f"flats_without_recipients={len(flat_ids_without_recipients)}"
        )
        logger.warning(
            "Food token notification completed with partial failures",
            extra={
                "event_id": str(event.id),
                "society_id": str(event.society_id),
                "failure_summary": failure_summary,
                "failed_recipients": failed_recipients,
                "flat_ids_without_recipients": flat_ids_without_recipients,
            },
        )
        db.add(
            AuditLog(
                society_id=event.society_id,
                entity_type="food_collection",
                entity_id=event.id,
                action="FOOD_TOKEN_NOTIFY_PARTIAL",
                reason=(
                    f"{failure_summary}; "
                    f"failed_flats={[flat_number_by_id.get(flat_id) for flat_id in tokens_by_flat.keys() if str(flat_id) in flat_ids_without_recipients]}"
                )[:255],
                performed_by=performed_by,
            )
        )


def _build_committee_action_session_key(*, member, inbound_message):
    return build_committee_action_session_key(
        member_id=str(getattr(member, "id", "")) if member else None,
        sender_id=(
            inbound_message.metadata.get("canonical_sender_id")
            if inbound_message is not None and inbound_message.metadata
            else None
        )
        or (inbound_message.sender_id if inbound_message is not None else None),
    )


def _prompt_for_pending_action_step(state: CommitteeActionSessionState, lang: str | None = None) -> str:
    prompts = {
        ("ADD_EXPENSE", "reason"): translate("committee.pending.add_expense.reason", lang),
        ("ADD_EXPENSE", "amount"): translate("committee.pending.add_expense.amount", lang),
        ("ADD_SPONSOR", "sponsor_type"): "Sponsor type? Reply: monetary or in-kind\nExpected next reply: `monetary` or `in-kind`.\nType `cancel` to stop.",
        ("ADD_SPONSOR", "sponsor_name"): "Sponsor name (or flat number). Example: Shree Caterers or A-101\nExpected next reply: sponsor name/flat.\nType `cancel` to stop.",
        ("ADD_SPONSOR", "amount_or_details"): "Share sponsor amount/details.\nExpected next reply: amount for monetary, or details for in-kind.\nType `cancel` to stop.",
        ("REFUND_SPONSOR", "contribution_code"): "Please share contribution code. Example: SP-001\nExpected next reply: contribution code.\nType `cancel` to stop.",
        ("REFUND_SPONSOR", "amount"): "Please share refund amount. Example: 500\nExpected next reply: numeric amount only.\nType `cancel` to stop.",
        ("REFUND_SPONSOR", "reason"): "Please share refund reason.\nExpected next reply: reason text.\nType `cancel` to stop.",
        ("REFUND_SPONSOR", "override_reason"): "This refund needs an override reason due to workflow state.\nExpected next reply: override reason text.\nType `cancel` to stop.",
        ("REMIND_FLAT", "flat_number"): translate("committee.pending.remind_flat.flat_number", lang),
        ("ANNOUNCE_EVENT", "message_body"): "Please type the event announcement text to send.\nType `cancel` to stop.",
        ("ANNOUNCE_SOCIETY", "message_body"): "Please type the society announcement text to send.\nType `cancel` to stop.",
    }
    return prompts[(state.action, state.step)]


def _add_sponsor_contribution(*, db, event, member, sponsor_type: str, sponsor_name: str, amount_or_details: str, override_reason: str | None = None):
    flat_id = None
    normalized_sponsor_type = sponsor_type.strip().lower()
    normalized_name = sponsor_name.strip()
    payload = amount_or_details.strip()

    flat = (
        db.query(Flat)
        .filter(
            Flat.flat_number == normalized_name,
            Flat.society_id == event.society_id,
        )
        .first()
    )
    if flat:
        flat_id = flat.id
        normalized_name = f"Flat {flat.flat_number}"

    if normalized_sponsor_type == "in-kind":
        ContributionService.add_contribution(
            db=db,
            event_id=event.id,
            contribution_type="in_kind",
            source_name=normalized_name,
            flat_id=flat_id,
            in_kind_details=payload,
            performed_by=member.id,
            notes="Via WhatsApp",
            override_reason=override_reason,
        )
        return success_response(
            "In-kind sponsor added successfully.",
            heading="Sponsor added",
            emoji="🤝",
        )

    amount = int(payload)
    ContributionService.add_contribution(
        db=db,
        event_id=event.id,
        contribution_type="sponsor",
        source_name=normalized_name,
        flat_id=flat_id,
        amount=amount,
        performed_by=member.id,
        notes="Via WhatsApp",
        override_reason=override_reason,
    )
    return success_response("Sponsor added successfully.", heading="Sponsor added", emoji="🤝")


def _build_reminder_preview(*, db, event, flat_number: str):
    flat = (
        db.query(Flat)
        .filter(
            Flat.flat_number == flat_number, Flat.society_id == event.society_id
        )
        .first()
    )

    if not flat:
        return error_response("Flat not found.")

    food_pass = (
        db.query(EventFoodPass)
        .filter(
            EventFoodPass.event_id == event.id,
            EventFoodPass.flat_id == flat.id,
            EventFoodPass.is_participating.is_(True),
        )
        .first()
    )

    if not food_pass:
        return error_response("Flat has not joined the event.")

    paid_amount = (
        db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
        .filter(Payment.event_id == event.id, Payment.flat_id == flat.id)
        .scalar()
    )

    refunded_amount = (
        db.query(func.coalesce(func.sum(Refund.amount), 0))
        .filter(
            Refund.event_id == event.id,
            Refund.flat_id == flat.id,
            Refund.status == "refunded",
        )
        .scalar()
    )

    pending_amount = food_pass.total_amount - paid_amount - refunded_amount
    if pending_amount <= 0:
        return success_response(
            f"{flat_number} has no pending payment.",
            heading="Payment Reminder",
            emoji="📢",
        )

    return success_response(
        join_lines(
            [
                f"Dear {flat_number},",
                f"Your pending amount for *{event.name}* is "
                f"{format_currency(pending_amount)}.",
                "Please pay at your convenience.",
                "",
                "Thank you.",
            ]
        ),
        heading="Payment Reminder",
        emoji="📢",
    )


def handle_committee_intent(
    *,
    db: Session,
    intent: str,
    message: str,
    event: Any,
    member: Any,
    inbound_message: InboundMessage | None = None,
    lang: str | None = None,
) -> str | None:
    committee_action_session_key = _build_committee_action_session_key(
        member=member,
        inbound_message=inbound_message,
    )
    pending_action_state = get_committee_action_session(committee_action_session_key)

    if intent in {"ADD_EXPENSE", "ADD_SPONSOR", "REFUND_SPONSOR", "REMIND_FLAT", "CLOSE_EVENT", "ANNOUNCE_EVENT", "ANNOUNCE_SOCIETY"}:
        clear_committee_action_session(committee_action_session_key)


    if intent == "ADD_EXPENSE":
        normalized_message, override_reason = _extract_override_reason(message)
        event_state = _event_state_for_intent(db=db, event=event) if override_reason else None
        can_execute, warning = can_execute_intent(
            member=member,
            intent=intent,
            event_state=event_state,
            override_reason=override_reason,
        )
        if not can_execute:
            return warning_response(warning or "Action is not allowed.")

        if not event:
            return error_response(translate("committee.common.no_active_event", lang))

        amount = parse_amount(normalized_message)
        reason = normalized_message.replace(str(amount), "").strip() if amount else ""

        has_direct_args = normalized_message.strip().lower() != "expense"
        if not has_direct_args:
            state = CommitteeActionSessionState(action="ADD_EXPENSE", step="reason")
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state, lang))

        if not reason:
            state = CommitteeActionSessionState(action="ADD_EXPENSE", step="reason")
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state, lang))

        if not amount:
            state = CommitteeActionSessionState(
                action="ADD_EXPENSE",
                step="amount",
                data={"reason": reason},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state, lang))

        clear_committee_action_session(committee_action_session_key)

        ExpenseService.add_expense(
            db=db,
            event_id=event.id,
            description=reason or "WhatsApp expense",
            amount=amount,
            performed_by=member.id,
            override_reason=override_reason or "Via WhatsApp",
        )
        return success_response(
            translate("committee.add_expense.added_message", lang, amount=format_currency(amount)),
            heading=translate("committee.add_expense.heading", lang),
            emoji="🧾",
        )

    if intent == "COMMITTEE_PENDING_ACTION" and pending_action_state:
        answer = (message or "").strip()
        state = pending_action_state

        if answer.lower() == "cancel":
            clear_committee_action_session(committee_action_session_key)
            return info_response(translate("committee.pending.cancelled", lang))

        if not event and state.action not in ANNOUNCE_INTENTS:
            clear_committee_action_session(committee_action_session_key)
            return error_response(translate("committee.common.no_active_event", lang))

        if state.action == "ADD_EXPENSE":
            if state.step == "reason":
                if not answer:
                    return error_response(translate("committee.pending.add_expense.reason_required", lang))
                state.data["reason"] = answer
                state.step = "amount"
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state, lang))

            if state.step == "amount":
                if not answer.isdigit():
                    return info_response(translate("committee.pending.add_expense.amount_numeric", lang))
                amount = int(answer)
                reason = state.data.get("reason") or "WhatsApp expense"
                clear_committee_action_session(committee_action_session_key)
                ExpenseService.add_expense(
                    db=db,
                    event_id=event.id,
                    description=reason,
                    amount=amount,
                    performed_by=member.id,
                    override_reason="Via WhatsApp",
                )
                return success_response(
                    translate("committee.add_expense.added_message", lang, amount=format_currency(amount)),
                    heading=translate("committee.add_expense.heading", lang),
                    emoji="🧾",
                )

        if state.action == "ADD_SPONSOR":
            if state.step == "sponsor_type":
                sponsor_type = answer.lower()
                if sponsor_type not in {"monetary", "in-kind"}:
                    return error_response("Sponsor type must be `monetary` or `in-kind`.")
                state.data["sponsor_type"] = sponsor_type
                state.step = "sponsor_name"
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))

            if state.step == "sponsor_name":
                if not answer:
                    return error_response("Sponsor name (or flat) is required.")
                state.data["sponsor_name"] = answer
                state.step = "amount_or_details"
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))

            if state.step == "amount_or_details":
                sponsor_type = state.data.get("sponsor_type", "")
                sponsor_name = state.data.get("sponsor_name", "")
                if sponsor_type == "monetary" and not answer.isdigit():
                    return info_response("Sponsor amount must be numeric. Example: 5000")
                if not answer:
                    return error_response("Sponsor amount/details is required.")
                clear_committee_action_session(committee_action_session_key)
                return _add_sponsor_contribution(
                    db=db,
                    event=event,
                    member=member,
                    sponsor_type=sponsor_type,
                    sponsor_name=sponsor_name,
                    amount_or_details=answer,
                )

        if state.action == "REFUND_SPONSOR":
            if state.step == "contribution_code":
                if not answer:
                    return error_response("Contribution code is required.")
                state.data["contribution_code"] = answer.upper()
                state.step = "amount"
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))

            if state.step == "amount":
                if not answer.isdigit():
                    return info_response("Refund amount must be numeric. Example: 500")
                state.data["amount"] = answer
                state.step = "reason"
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))

            if state.step == "reason":
                if not answer:
                    return error_response("Refund reason is required.")
                state.data["reason"] = answer
                try:
                    ContributionRefundService.process_refund(
                        db=db,
                        event_id=event.id,
                        contribution_code=state.data["contribution_code"],
                        amount=int(state.data["amount"]),
                        reason=answer,
                        performed_by=member.id,
                    )
                except Exception as exc:
                    if "requires override" in str(exc).lower():
                        state.step = "override_reason"
                        save_committee_action_session(committee_action_session_key, state)
                        return info_response(_prompt_for_pending_action_step(state))
                    clear_committee_action_session(committee_action_session_key)
                    return error_response(str(exc))
                clear_committee_action_session(committee_action_session_key)
                return success_response(
                    f"Sponsor refund processed ({state.data['contribution_code']}).",
                    heading="Refund processed",
                    emoji="↩️",
                )

            if state.step == "override_reason":
                if not answer:
                    return error_response("Override reason is required.")
                try:
                    ContributionRefundService.process_refund(
                        db=db,
                        event_id=event.id,
                        contribution_code=state.data["contribution_code"],
                        amount=int(state.data["amount"]),
                        reason=state.data["reason"],
                        performed_by=member.id,
                        override_reason=answer,
                    )
                except Exception as exc:
                    return error_response(str(exc))
                clear_committee_action_session(committee_action_session_key)
                return success_response(
                    f"Sponsor refund processed ({state.data['contribution_code']}).",
                    heading="Refund processed",
                    emoji="↩️",
                )

        if state.action == "REMIND_FLAT":
            if state.step == "flat_number":
                if not answer:
                    return error_response("Flat number is required.")
                clear_committee_action_session(committee_action_session_key)
                return _build_reminder_preview(db=db, event=event, flat_number=answer)

        if state.action in ANNOUNCE_INTENTS:
            if state.step == "message_body":
                if not answer:
                    return error_response("Announcement body cannot be empty.")
                if len(answer) > ANNOUNCE_MAX_WHATSAPP_TEXT_LENGTH:
                    return error_response(
                        f"Announcement is too long ({len(answer)} chars). Max allowed is {ANNOUNCE_MAX_WHATSAPP_TEXT_LENGTH}."
                    )
                clear_committee_action_session(committee_action_session_key)
                try:
                    queue_result = AnnouncementManager.queue(
                        db=db,
                        member=member,
                        event=event,
                        message_body=answer,
                        scope="event" if state.action == "ANNOUNCE_EVENT" else "society",
                    )
                except ValueError as exc:
                    return error_response(str(exc))
                return success_response(
                    (
                        "Announcement accepted for processing. "
                        f"Accepted: {queue_result.accepted_count}, "
                        f"Skipped: {queue_result.skipped_count}, "
                        f"Announcement ID: {queue_result.announcement_id}"
                    ),
                    heading="Announcement queued",
                    emoji="📣",
                )

    event_session_key = build_event_creation_session_key(
        member_id=str(getattr(member, "id", "")) if member else None,
        sender_id=(
            inbound_message.metadata.get("canonical_sender_id")
            if inbound_message is not None
            else None
        )
        or (inbound_message.sender_id if inbound_message is not None else None),
    )

    if intent == "ADD_EVENT":
        if not is_action_allowed(member.role, "ADD_EVENT"):
            return warning_response("Only Chairman or Secretary can add events.")

        trimmed_message = message.strip()
        parsed, error = parse_event_creation(trimmed_message)

        if parsed:
            event_data = parsed
            created_event = EventService.create_event(
                db=db,
                society_id=member.society_id,
                name=event_data["name"],
                event_date=event_data["event_date"],
                food_types=event_data["food_types"],
                charge_per_adult=event_data["charge_per_adult"],
                charge_per_child=event_data["charge_per_child"],
                payment_deadline=event_data["payment_deadline"],
                created_by=member.id,
            )
            clear_event_creation_session(event_session_key)

            return success_response(
                join_lines(
                    [
                        f"Event: {created_event.name}",
                        f"Date: {format_datetime(created_event.event_date)}",
                        f"Food: {', '.join(created_event.food_types)}",
                        f"Adult: {format_currency(created_event.charge_per_adult)}",
                        f"Child: {format_currency(created_event.charge_per_child)}",
                        f"Deadline: {format_datetime(created_event.payment_deadline)}",
                    ]
                ),
                heading="Event created",
                emoji="📅",
            )

        if trimmed_message.lower() == "add event":
            return _start_event_creation_wizard(session_key=event_session_key)

        existing_state = get_event_creation_session(event_session_key)
        if existing_state:
            return _handle_event_creation_wizard_step(
                db=db,
                member=member,
                message=trimmed_message,
                session_key=event_session_key,
                state=existing_state,
            )

        if error and "Missing fields" in error:
            return _start_event_creation_wizard(session_key=event_session_key)

        if error:
            return error_response(error)

    if intent == "ACTIVATE_EVENT":
        if not is_action_allowed(member.role, "ADD_EVENT"):
            return warning_response("Only Chairman or Secretary can activate events.")

        target_event = event
        if not target_event:
            target_event = (
                db.query(Event)
                .filter(Event.society_id == member.society_id)
                .order_by(Event.created_at.desc())
                .first()
            )

        if not target_event:
            return error_response("No event found to activate. Please create an event first.")

        try:
            EventService.activate_event(
                db=db,
                event_id=target_event.id,
                performed_by=member.id,
                override_reason="Via WhatsApp",
            )
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Event activated: {target_event.name}",
            heading="Event activated",
            emoji="🟢",
        )

    if intent == "LOCK_PASSES":
        if not is_action_allowed(member.role, "ADD_EVENT"):
            return warning_response("Only Chairman or Secretary can lock passes.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        try:
            EventService.lock_passes(
                db=db,
                event_id=event.id,
                performed_by=member.id,
                override_reason="Via WhatsApp",
            )
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Passes locked for event: {event.name}",
            heading="Passes locked",
            emoji="🔐",
        )

    if intent == "START_EVENT":
        if not is_action_allowed(member.role, "ADD_EVENT"):
            return warning_response("Only Chairman or Secretary can start event day.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        try:
            EventService.start_event_day(
                db=db,
                event_id=event.id,
                performed_by=member.id,
                override_reason="Via WhatsApp",
            )
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Event day started: {event.name}",
            heading="Event started",
            emoji="🎉",
        )

    if intent == "GENERATE_FOOD_TOKENS":
        normalized_message, override_reason = _extract_override_reason(message)
        if not event:
            return error_response("No active event found. Please contact committee.")
        try:
            tokens = FoodCollectionService.generate_tokens_for_event(
                db=db,
                event_id=event.id,
                performed_by=member.id,
                override_reason=override_reason,
                notify_callback=lambda *, event, generated_tokens: _notify_generated_food_tokens(
                    db=db,
                    event=event,
                    generated_tokens=generated_tokens,
                    performed_by=member.id,
                ),
            )
        except Exception as exc:
            return error_response(str(exc))
        return success_response(
            f"Generated {len(tokens)} food tokens for {event.name}. Share 'my tokens' with members.",
            heading="Food tokens generated",
            emoji="🎟️",
        )

    if intent == "OPEN_FOOD_COUNTER":
        normalized_message, override_reason = _extract_override_reason(message)
        if not event:
            return error_response("No active event found. Please contact committee.")
        auto_close_minutes = parse_amount(normalized_message) or 120
        try:
            counter = FoodCollectionService.open_food_counter(
                db=db,
                event_id=event.id,
                performed_by=member.id,
                auto_close_minutes=auto_close_minutes,
                override_reason=override_reason,
            )
        except Exception as exc:
            return error_response(str(exc))

        announcement_message = _build_food_counter_open_announcement(
            event_name=event.name,
            closes_at=counter.closes_at,
        )
        try:
            AnnouncementManager.queue(
                db=db,
                member=member,
                event=event,
                message_body=announcement_message,
                scope="event",
            )
        except Exception:
            logger.exception(
                "Failed to queue food counter open announcement",
                extra={
                    "event_id": str(getattr(event, "id", "")),
                    "society_id": str(getattr(member, "society_id", "")),
                    "member_id": str(getattr(member, "id", "")),
                },
            )

        closes_at_text = format_datetime(counter.closes_at) if counter.closes_at else "N/A"
        return success_response(
            join_lines([
                "Food counter is now open.",
                f"Auto-closes at: {closes_at_text}",
                "Ask members to keep QR or token ready.",
            ]),
            heading="Food counter opened",
            emoji="🍽️",
        )

    if intent in {"VERIFY_FOOD_TOKEN", "SCAN_FOOD_QR"}:
        normalized_message, override_reason = _extract_override_reason(message)
        if not event:
            return error_response("No active event found. Please contact committee.")
        prefix = "verify food token" if intent == "VERIFY_FOOD_TOKEN" else "scan food qr"
        token_code = _parse_token_after_prefix(normalized_message, prefix=prefix)
        if not token_code:
            return error_response(f"Token is required. Example: {prefix} AB2K9M")

        method = "MANUAL_TOKEN" if intent == "VERIFY_FOOD_TOKEN" else "QR_SCAN"
        try:
            served = FoodCollectionService.verify_and_serve_token(
                db=db,
                event_id=event.id,
                token_code=token_code,
                method=method,
                performed_by=member.id,
                override_reason=override_reason,
            )
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Served token {served.token_code} ({served.food_type}).",
            heading="Plate served",
            emoji="✅",
        )

    if intent == "SERVE_FOOD_FLAT":
        normalized_message, override_reason = _extract_override_reason(message)
        if not event:
            return error_response("No active event found. Please contact committee.")
        flat_number = parse_target_flat(normalized_message)
        if not flat_number:
            raw = (normalized_message or "").strip()
            flat_number = raw[len("serve flat"):].strip() if raw.lower().startswith("serve flat") else None
        if not flat_number:
            return info_response("Flat number is required. Example: serve flat A-101")

        flat = (
            db.query(Flat)
            .filter(
                Flat.society_id == event.society_id,
                Flat.flat_number == flat_number,
            )
            .first()
        )
        if not flat:
            return error_response("Flat not found.")
        try:
            served = FoodCollectionService.serve_by_flat_lookup(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                performed_by=member.id,
                override_reason=override_reason,
            )
        except Exception as exc:
            return error_response(str(exc))
        return success_response(
            f"Served {flat.flat_number} via no-token fallback ({served.token_code}).",
            heading="Plate served",
            emoji="✅",
        )

    if intent == "FLAT_PASS_STATUS":
        if not event:
            return error_response("No active event found. Please contact committee.")
        raw = (message or "").strip()
        flat_number = raw[len("flat passes"):].strip() if raw.lower().startswith("flat passes") else None
        if not flat_number:
            return info_response("Flat number is required. Example: flat passes A-101")
        try:
            summary = FoodCollectionService.committee_flat_status(
                db=db,
                event_id=event.id,
                flat_number=flat_number,
            )
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            join_lines([
                f"Flat: {summary['flat_number']}",
                f"Total: {summary['total_passes']}",
                f"Served: {summary['served']}",
                f"Remaining: {summary['remaining']}",
                *( [f"Fallback served (no-token): {summary['fallback_served']}"] if summary.get('fallback_served') else []),
            ]),
            heading="Flat pass status",
            emoji="📊",
        )

    if intent == "TOKEN_STATUS":
        if not event:
            return error_response("No active event found. Please contact committee.")
        token_code = _parse_token_after_prefix(message, prefix="token status")
        if not token_code:
            return info_response("Token is required. Example: token status AB2K9M")
        try:
            token = FoodCollectionService.inspect_token(
                db=db,
                event_id=event.id,
                token_code=token_code,
            )
        except Exception as exc:
            return error_response(str(exc))
        status = "Served" if token.served_at else "Not served"
        return success_response(
            join_lines([
                f"Token: {token.token_code}",
                f"Food type: {token.food_type}",
                f"Status: {status}",
            ]),
            heading="Token status",
            emoji="🔎",
        )

    if intent == "FOOD_DASHBOARD":
        if not event:
            return error_response("No active event found. Please contact committee.")
        dashboard = FoodCollectionService.dashboard(db=db, event_id=event.id, recent_limit=5)
        by_type_lines = [
            f"{food_type.title()}: {metrics['served']}/{metrics['total']} served"
            for food_type, metrics in dashboard["by_type"].items()
        ]
        recent_lines = [
            (
                f"{row['token']} | {row.get('flat_number') or row.get('flat_id') or '-'} | "
                f"{row['food_type']} | {format_datetime(row['served_at'])}"
                + (" | Fallback serve" if row.get('is_fallback') else "")
            )
            for row in dashboard["recent_served"]
        ] or ["No plates served yet."]
        return success_response(
            join_lines([
                f"Total: {dashboard['total_plates']}",
                f"Served: {dashboard['served_plates']}",
                f"Remaining: {dashboard['remaining_plates']}",
                "",
                "By type:",
                *by_type_lines,
                "",
                "Recent served:",
                *recent_lines,
            ]),
            heading="Food dashboard",
            emoji="📈",
        )

    if intent == "CLOSE_EVENT":
        can_execute, warning = can_execute_intent(
            member=member,
            intent=intent,
            event_state=None,
            override_reason=None,
        )
        if not can_execute:
            return warning_response(warning or "Action is not allowed.")

        reason = parse_reason(message, command_prefixes=("close event",))
        if not reason or not reason.strip():
            return info_response("Please provide a close reason. Example: close event reason settlement completed")

        target_event = event
        if not target_event:
            target_event = (
                db.query(Event)
                .filter(Event.society_id == member.society_id)
                .order_by(Event.created_at.desc())
                .first()
            )

        if not target_event:
            return error_response("No event found to close. Please contact committee.")

        try:
            EventService.close_event(
                db=db,
                event_id=target_event.id,
                performed_by=member.id,
                override_reason=reason.strip(),
            )
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Event closed: {target_event.name}",
            heading="Event closed",
            emoji="🔒",
        )

    if intent == "PENDING_PAYMENTS":
        if not is_action_allowed(member.role, "PAY"):
            return warning_response("This action normally requires Treasurer approval.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        pending = PendingPaymentReport.get_pending_flats(
            db=db, event_id=event.id, society_id=event.society_id
        )

        if not pending:
            return success_response(
                "All flats have completed payments.",
                heading="Pending Payments",
                emoji="🎉",
            )

        lines = [format_heading("Pending Payments", "⏳")]
        for p in pending:
            lines.append(f"{p['flat']} – Pending {format_currency(p['pending'])}")

        return success_response(join_lines(lines))

    if intent == "PAYMENT_REQUESTS":
        if not is_action_allowed(member.role, "PAY"):
            return warning_response("Only Treasurer can view payment requests.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        requests = PaymentRequestService.list_requests(db=db, event_id=event.id)

        if not requests:
            return success_response(
                "No payment requests found.", heading="Payment Requests", emoji="📥"
            )

        lines = [format_heading("Payment Requests", "📥")]
        for request, flat in requests:
            requester = getattr(
                request,
                "requested_by_mapping_id",
                getattr(request, "requested_by", "unknown")
            )
            lines.append(
                f"{request.request_code} | {flat.flat_number} | "
                f"{format_currency(request.amount)} | "
                f"{requester} | {request.status}"
            )

        return success_response(join_lines(lines))

    if intent == "REFUND_REQUESTS":
        if not is_action_allowed(member.role, "REFUND"):
            return warning_response("Only Treasurer can view refund requests.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        requests = RefundRequestService.list_requests(db=db, event_id=event.id)

        if not requests:
            return success_response(
                "No refund requests found.", heading="Refund Requests", emoji="📤"
            )

        lines = [format_heading("Refund Requests", "📤")]
        for request, flat in requests:
            requester = getattr(
                request,
                "requested_by_mapping_id",
                getattr(request, "requested_by", "unknown")
            )
            lines.append(
                f"{request.request_code} | {flat.flat_number} | "
                f"{format_currency(request.amount)} | "
                f"{requester} | {request.status}"
            )

        return success_response(join_lines(lines))


    export_sender_id = (
        inbound_message.metadata.get("canonical_sender_id")
        if inbound_message is not None and inbound_message.metadata
        else None
    ) or (inbound_message.sender_id if inbound_message is not None else None)

    session_key = build_export_session_key(
        member_id=(str(getattr(member, "id", "")) if export_sender_id else None) if member else None,
        sender_id=export_sender_id,
    )

    if intent == "REPORT_OPTIONS":
        report_options = _report_options(role=member.role)
        event_options = _recent_event_options(db=db, society_id=member.society_id)
        selected_event_id = str(event.id) if event else None
        if selected_event_id and event_options and selected_event_id not in {item["id"] for item in event_options}:
            selected_event_id = None
        save_export_session(
            session_key,
            ExportSessionState(
                options=report_options,
                event_id=selected_event_id,
                event_options=event_options,
            ),
        )
        return success_response(
            _format_report_options_with_event(
                options=report_options,
                event_options=event_options,
                selected_event_id=selected_event_id,
            )
        )


    if intent == "EXPORT_SELECTION":
        session = get_export_session(session_key)
        if not session or not session.options:
            return info_response("No active export session. Send `report options` first.")

        tokens = (message or "").strip().lower().split()
        normalized_message = (message or "").strip().lower()

        if len(tokens) >= 2 and tokens[0] == "event" and tokens[1].isdigit():
            selected_event_index = int(tokens[1]) - 1
            if selected_event_index < 0 or selected_event_index >= len(session.event_options):
                return error_response("Invalid event selection. Reply with `event <number>` from report options.")
            session.event_id = session.event_options[selected_event_index]["id"]
            save_export_session(session_key, session)
            return success_response(
                _format_report_options_with_event(
                    options=session.options,
                    event_options=session.event_options,
                    selected_event_id=session.event_id,
                )
            )

        selected_option = None
        selected_index = None
        selected_command_key = None

        if normalized_message.startswith("export::"):
            selected_command_key = normalized_message.removeprefix("export::").strip()

        if selected_command_key:
            selected_option = next(
                (
                    option
                    for option in session.options
                    if (option.get("command_key") or "").strip().lower() == selected_command_key
                ),
                None,
            )

        if len(tokens) >= 2 and tokens[1].isdigit():
            selected_index = int(tokens[1]) - 1
        elif len(tokens) == 1 and tokens[0].isdigit():
            selected_index = int(tokens[0]) - 1

        if selected_option is None and selected_index is not None:
            if 0 <= selected_index < len(session.options):
                selected_option = session.options[selected_index]
        if not selected_option:
            return error_response(
                "Invalid selection. Use `event <number>` or `export <number>` from report options."
            )

        try:
            result = WhatsAppReportExportService.export(
                db=db,
                member=member,
                event=event,
                category=selected_option["category"],
                report=selected_option["report_key"],
                format="pdf",
                event_id=session.event_id,
            )
        except ValueError as exc:
            return error_response(str(exc))
        except Exception as exc:
            return error_response(f"Export failed: {exc}")

        clear_export_session(session_key)
        return _dispatch_export_result(
            result=result,
            member=member,
            inbound_message=inbound_message,
        )


    if intent == "LIST_COMMITTEE_MEMBERS":
        include_inactive = "all" in (message or "").lower()
        members = CommitteeMemberService.list_members(
            db=db,
            society_id=member.society_id,
            include_inactive=include_inactive,
        )
        if not members:
            return info_response("No committee members found.")

        lines = [format_heading("Committee members", "👥"), ""]
        for entry in members:
            status = "active" if entry.is_active else "inactive"
            lines.append(f"- {entry.name} ({entry.role}) | {entry.phone_number} | id={entry.id} | {status}")
        return success_response(join_lines(lines))

    if intent == "ADD_COMMITTEE_MEMBER":
        parsed = _parse_add_committee_member_args(message)
        if not parsed:
            return info_response(
                "Usage: add committee member <name>|<phone>|<role>\n"
                "Roles: chairman, treasurer, secretary, committee_member"
            )

        name, phone, role = parsed
        try:
            created = CommitteeMemberService.add_member(
                db=db,
                society_id=member.society_id,
                name=name,
                phone_number=phone,
                role=role,
                performed_by=member.id,
            )
        except PermissionError as exc:
            return warning_response(str(exc))
        except ValueError as exc:
            return error_response(str(exc))
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Committee member saved: {created.name} ({created.role})",
            heading="Committee updated",
            emoji="✅",
        )

    if intent == "REMOVE_COMMITTEE_MEMBER":
        member_id = _parse_member_id(message, prefix="remove committee member")
        if not member_id:
            return info_response("Usage: remove committee member <member_id>")

        try:
            removed = CommitteeMemberService.remove_member(
                db=db,
                society_id=member.society_id,
                member_id=member_id,
                performed_by=member.id,
            )
        except PermissionError as exc:
            return warning_response(str(exc))
        except ValueError as exc:
            return error_response(str(exc))
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Committee member removed: {removed.name}",
            heading="Committee updated",
            emoji="🗑️",
        )

    if intent == "CHANGE_COMMITTEE_ROLE":
        parsed = _parse_member_id_and_role(message, prefix="change committee role")
        if not parsed:
            return info_response(
                "Usage: change committee role <member_id> <role>\n"
                "Roles: chairman, treasurer, secretary, committee_member"
            )

        member_id, role = parsed

        try:
            updated = CommitteeMemberService.change_role(
                db=db,
                society_id=member.society_id,
                member_id=member_id,
                role=role,
                performed_by=member.id,
            )
        except PermissionError as exc:
            return warning_response(str(exc))
        except ValueError as exc:
            return error_response(str(exc))
        except Exception as exc:
            return error_response(str(exc))

        return success_response(
            f"Role updated: {updated.name} is now {updated.role}",
            heading="Committee updated",
            emoji="🔁",
        )


    if intent == "PARTICIPATION_REPORT":
        if not event:
            return error_response("No active event found. Please contact committee.")

        report = EventParticipationReport.generate(
            db=db, event_id=event.id, society_id=event.society_id
        )

        participating = report["participating"]
        not_participating = report["not_participating"]

        lines = [
            format_heading(f"Participation Report ({event.name})", "🎫"),
            "",
            "*Joined*:",
            ", ".join(participating) if participating else "None",
            "",
            "*Not Joined*:",
            ", ".join(not_participating) if not_participating else "None",
        ]
        return success_response(join_lines(lines))

    if intent == "REMIND_FLAT":
        can_execute, warning = can_execute_intent(
            member=member,
            intent=intent,
            event_state=None,
            override_reason=None,
        )
        if not can_execute:
            return warning_response(warning or "Action is not allowed.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        parts = message.split()
        if len(parts) < 2:
            state = CommitteeActionSessionState(action="REMIND_FLAT", step="flat_number")
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        flat_number = parts[1]

        return _build_reminder_preview(db=db, event=event, flat_number=flat_number)

    if intent in ANNOUNCE_INTENTS:
        can_execute, warning = can_execute_intent(
            member=member,
            intent=intent,
            event_state=None,
            override_reason=None,
        )
        if not can_execute:
            return warning_response(warning or "Action is not allowed.")

        command_prefix = "announce event" if intent == "ANNOUNCE_EVENT" else "announce society"
        announcement_body = _extract_announcement_body(message=message, command_prefix=command_prefix)

        if not announcement_body.strip():
            state = CommitteeActionSessionState(action=intent, step="message_body")
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        if len(announcement_body) > ANNOUNCE_MAX_WHATSAPP_TEXT_LENGTH:
            return error_response(
                f"Announcement is too long ({len(announcement_body)} chars). Max allowed is {ANNOUNCE_MAX_WHATSAPP_TEXT_LENGTH}."
            )

        try:
            queue_result = AnnouncementManager.queue(
                db=db,
                member=member,
                event=event,
                message_body=announcement_body,
                scope="event" if intent == "ANNOUNCE_EVENT" else "society",
            )
        except ValueError as exc:
            return error_response(str(exc))

        return success_response(
            (
                "Announcement accepted for processing. "
                f"Accepted: {queue_result.accepted_count}, "
                f"Skipped: {queue_result.skipped_count}, "
                f"Announcement ID: {queue_result.announcement_id}"
            ),
            heading="Announcement queued",
            emoji="📣",
        )

    if intent == "APPROVE":
        if not is_action_allowed(member.role, "ALL"):
            return warning_response("Only Chairman can approve users.")

        parts = message.split()
        if len(parts) < 3:
            return info_response("Example: approve user REQ-003")

        request_code = parts[2].upper()

        AdminApprovalService.approve_user(
            db=db,
            request_code=request_code,
            performed_by=member.id,
        )

        return success_response(f"User approved ({request_code})")

    if intent == "APPROVE_PAYMENT":
        if not is_action_allowed(member.role, "PAY"):
            return warning_response("Only Treasurer can approve payments.")

        parts = message.split()
        if len(parts) < 3:
            return info_response("Example: approve payment PAY-001")

        request_code = parts[2].upper()
        request = PaymentRequestService.get_request_by_code(
            db=db, request_code=request_code
        )
        if not request:
            return error_response("Payment request not found.")
        if request.status != "requested":
            return warning_response("Payment request already processed.")

        PaymentRequestService.approve_request(
            db=db, request=request, performed_by=member.id
        )
        return success_response(f"Payment approved ({request_code})")

    if intent == "APPROVE_REFUND":
        if not is_action_allowed(member.role, "REFUND"):
            return warning_response("Only Treasurer can approve refunds.")

        parts = message.split()
        if len(parts) < 3:
            return info_response("Example: approve refund REF-001")

        request_code = parts[2].upper()
        request = RefundRequestService.get_request_by_code(
            db=db, request_code=request_code
        )
        if not request:
            return error_response("Refund request not found.")
        if request.status != "requested":
            return warning_response("Refund request already processed.")

        RefundRequestService.approve_request(
            db=db, request=request, performed_by=member.id
        )
        return success_response(f"Refund approved ({request_code})")

    if intent == "PENDING_USERS":
        if not is_action_allowed(member.role, "ALL"):
            return warning_response("Only Chairman can view pending users.")

        latest_event = event
        if not latest_event:
            return error_response("No society context found.")

        society_id = latest_event.society_id

        pending = AdminOnboardingQueryService.list_pending_users(
            db=db, society_id=society_id
        )

        if not pending:
            return success_response(
                "No pending user requests.", heading="Pending Join Requests", emoji="🎉"
            )

        lines = [format_heading("Pending Join Requests", "⏳")]
        for pending_user, flat in pending:
            lines.append(
                f"Request: *{pending_user.request_code}*\n"
                f"Flat: {flat.flat_number}\n"
                f"Requested At: {format_datetime(pending_user.created_at)}\n"
                f"---"
            )

        return success_response(join_lines(lines))

    if intent == "ADD_SPONSOR":
        normalized_message, override_reason = _extract_override_reason(message)
        event_state = _event_state_for_intent(db=db, event=event) if override_reason else None
        can_execute, warning = can_execute_intent(
            member=member,
            intent=intent,
            event_state=event_state,
            override_reason=override_reason,
        )
        if not can_execute:
            return warning_response(warning or "Action is not allowed.")

        if not event:
            return error_response("No active event found. Please contact committee.")

        raw = normalized_message.replace("add sponsor", "", 1).strip()

        if not raw:
            state = CommitteeActionSessionState(action="ADD_SPONSOR", step="sponsor_type")
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        if "in-kind" in raw:
            before, after = raw.split("in-kind", 1)
            sponsor_name = before.strip()
            details = after.strip()
            if not sponsor_name:
                state = CommitteeActionSessionState(
                    action="ADD_SPONSOR",
                    step="sponsor_name",
                    data={"sponsor_type": "in-kind"},
                )
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))
            if not details:
                state = CommitteeActionSessionState(
                    action="ADD_SPONSOR",
                    step="amount_or_details",
                    data={"sponsor_type": "in-kind", "sponsor_name": sponsor_name},
                )
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))
            return _add_sponsor_contribution(
                db=db,
                event=event,
                member=member,
                sponsor_type="in-kind",
                sponsor_name=sponsor_name,
                amount_or_details=details,
                override_reason=override_reason,
            )

        parts = raw.split()
        if len(parts) < 2:
            state = CommitteeActionSessionState(
                action="ADD_SPONSOR",
                step="amount_or_details",
                data={"sponsor_type": "monetary", "sponsor_name": raw},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        try:
            int(parts[-1])
        except ValueError:
            state = CommitteeActionSessionState(
                action="ADD_SPONSOR",
                step="sponsor_type",
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        sponsor_name = " ".join(parts[:-1]).strip()
        amount = parts[-1]
        if not sponsor_name:
            state = CommitteeActionSessionState(
                action="ADD_SPONSOR",
                step="sponsor_name",
                data={"sponsor_type": "monetary"},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        return _add_sponsor_contribution(
            db=db,
            event=event,
            member=member,
            sponsor_type="monetary",
            sponsor_name=sponsor_name,
            amount_or_details=amount,
            override_reason=override_reason,
        )

    if intent == "REFUND_SPONSOR":
        normalized_message, override_reason = _extract_override_reason(message)
        event_state = _event_state_for_intent(db=db, event=event) if override_reason else None
        can_execute, warning = can_execute_intent(
            member=member,
            intent=intent,
            event_state=event_state,
            override_reason=override_reason,
        )
        if not can_execute:
            return warning_response(warning or "Action is not allowed.")

        parts = normalized_message.split()

        if len(parts) < 3:
            state = CommitteeActionSessionState(action="REFUND_SPONSOR", step="contribution_code")
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        contribution_code = parts[2]

        # ✅ amount is ALWAYS the token after contribution code
        if len(parts) < 4:
            state = CommitteeActionSessionState(
                action="REFUND_SPONSOR",
                step="amount",
                data={"contribution_code": contribution_code.upper()},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))
        try:
            amount = int(parts[3])
        except ValueError:
            state = CommitteeActionSessionState(
                action="REFUND_SPONSOR",
                step="amount",
                data={"contribution_code": contribution_code.upper()},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        # reason = everything after 'reason'
        if "reason" not in parts:
            state = CommitteeActionSessionState(
                action="REFUND_SPONSOR",
                step="reason",
                data={"contribution_code": contribution_code.upper(), "amount": str(amount)},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        reason_index = parts.index("reason")
        reason = " ".join(parts[reason_index + 1 :]).strip()

        if not reason:
            state = CommitteeActionSessionState(
                action="REFUND_SPONSOR",
                step="reason",
                data={"contribution_code": contribution_code.upper(), "amount": str(amount)},
            )
            save_committee_action_session(committee_action_session_key, state)
            return info_response(_prompt_for_pending_action_step(state))

        try:
            ContributionRefundService.process_refund(
                db=db,
                event_id=event.id,
                contribution_code=contribution_code,
                amount=amount,
                reason=reason,
                performed_by=member.id,
                override_reason=override_reason,
            )
        except Exception as exc:
            if "requires override" in str(exc).lower():
                state = CommitteeActionSessionState(
                    action="REFUND_SPONSOR",
                    step="override_reason",
                    data={
                        "contribution_code": contribution_code.upper(),
                        "amount": str(amount),
                        "reason": reason,
                    },
                )
                save_committee_action_session(committee_action_session_key, state)
                return info_response(_prompt_for_pending_action_step(state))
            return error_response(str(exc))

        return success_response(
            f"Sponsor refund processed ({contribution_code}).",
            heading="Refund processed",
            emoji="↩️",
        )

    return None
