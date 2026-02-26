#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhatsApp UI routing and command handling."""

from datetime import timedelta

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.channels.whatsapp.constants import (
    WHATSAPP_SIGNATURE_HEADER,
    WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE,
)
from app.db.session import SessionLocal
from app.db.models import Event, MemberIdentity, UserFlatMapping
from app.whatsapp.router import detect_whatsapp_intent
from app.whatsapp.intents import WHATSAPP_INTENTS
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_exportable_report_options,
    resolve_report_entry,
)
from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService
from app.modules.users.user_query_service import UserQueryService
from app.modules.onboarding.join_code_service import JoinCodeService
from app.modules.onboarding.admin_query_service import AdminOnboardingQueryService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.commands.handlers.common import (
    get_latest_event,
    get_latest_event_for_society,
    resolve_flat,
    resolve_sender_society_id,
)
from app.whatsapp.response_templates import format_currency
from app.whatsapp.ui import (
    add_or_update_pass_prompt,
    build_committee_approvals_sections,
    build_committee_operations_more_sections,
    build_committee_operations_sections,
    build_committee_reports_sections,
    build_committee_sections,
    build_finance_sections,
    build_main_dashboard_sections,
    build_make_payment_sections,
    build_my_account_sections,
    build_participation_sections,
    build_payments_sections,
    build_reports_sections,
    build_society_sections,
    format_financial_overview,
    payment_custom_amount_prompt,
    refund_request_prompt,
)
from app.utils.guards import ensure_committee_member, ensure_member_of_society, normalize_phone
from app.permissions.command_policy import get_event_state, is_member_action_visible
from app.utils.logger import logger
from app.utils.time import utc_now
from app.whatsapp.export_session import (
    ExportSessionState,
    build_export_session_key,
    get_export_session,
    save_export_session,
)
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

WHATSAPP_LIST_MAX_ROWS = 10
WHATSAPP_MORE_REPORTS_ROW_ID = "export::more-reports"
WHATSAPP_APPROVAL_ROW_LIMIT = 10
WHATSAPP_REPORT_EVENT_ROW_PREFIX = "report-event::"
WHATSAPP_FINANCE_EVENT_ROW_PREFIX = "finance-event::"

FINANCE_EVENT_ACTIONS = {"VIEW_BALANCE", "MAKE_PAYMENT"}

REPORT_INTENTS_REQUIRING_EVENT = {"SUMMARY", "BLOCK_REPORT", "PARTICIPATION_REPORT"}
REPORT_AUTO_EVENT_STATES = {"ACTIVE", "LOCKED", "EVENT_DAY"}

def _default_report_event_id(event) -> str | None:
    if not event:
        return None
    status = (getattr(event, "status", "") or "").upper()
    if status in REPORT_AUTO_EVENT_STATES:
        return str(event.id)
    return None


def _report_page_option_limit(*, total_options: int, page_size: int = WHATSAPP_LIST_MAX_ROWS) -> int:
    if page_size <= 1:
        return 1
    return page_size - 1 if total_options > page_size else page_size


def _chunk_report_options(options: list[dict], page_size: int = WHATSAPP_LIST_MAX_ROWS) -> list[list[dict]]:
    if page_size <= 0:
        page_size = WHATSAPP_LIST_MAX_ROWS
    return [options[idx : idx + page_size] for idx in range(0, len(options), page_size)]


def _normalize_report_page(page_index: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return page_index % total_pages


def _next_report_page(current_page: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return (current_page + 1) % total_pages




def _get_latest_event_in_context(*, db, society_id):
    event = get_latest_event_for_society(db, society_id)
    if event:
        return event
    return get_latest_event(db)


def _recent_report_events(*, db, society_id) -> list[Event]:
    if not society_id:
        return []
    cutoff = utc_now() - timedelta(days=365)
    return (
        db.query(Event)
        .filter(Event.society_id == society_id, Event.event_date >= cutoff)
        .order_by(Event.event_date.desc())
        .limit(9)
        .all()
    )


def _build_report_event_sections(events: list[Event]) -> list[dict]:
    rows = [
        {
            "id": f"{WHATSAPP_REPORT_EVENT_ROW_PREFIX}{event.id}",
            "title": (event.name or "Event")[:24],
            "description": f"{event.event_date.strftime('%d %b %Y %H:%M')} · {event.status}",
        }
        for event in events
    ]
    if not rows:
        rows.append(
            {
                "id": "menu",
                "title": "Main Menu",
                "description": "No events found.",
            }
        )
    return [{"title": "Select event", "rows": rows}]


def _parse_report_event_selection(message_text: str) -> str | None:
    text = (message_text or "").strip().lower()
    prefix = WHATSAPP_REPORT_EVENT_ROW_PREFIX
    if not text.startswith(prefix):
        return None
    return text[len(prefix):].strip() or None




def _recent_member_events(*, db, sender_id: str) -> list[Event]:
    normalized_sender = normalize_phone(sender_id)
    if not normalized_sender:
        return []

    candidate_ids = {normalized_sender}
    if len(normalized_sender) > 10:
        candidate_ids.add(normalized_sender[-10:])

    mappings = (
        db.query(UserFlatMapping.society_id)
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(
            MemberIdentity.normalized_identifier.in_(tuple(candidate_ids)),
            UserFlatMapping.is_active.is_(True),
        )
        .distinct()
        .all()
    )
    society_ids = [m.society_id for m in mappings if getattr(m, "society_id", None)]
    if not society_ids:
        return []

    return (
        db.query(Event)
        .filter(Event.society_id.in_(tuple(society_ids)))
        .order_by(Event.event_date.desc())
        .limit(9)
        .all()
    )


def _build_finance_event_sections(events: list[Event]) -> list[dict]:
    rows = [
        {
            "id": f"{WHATSAPP_FINANCE_EVENT_ROW_PREFIX}{event.id}",
            "title": (event.name or "Event")[:24],
            "description": f"{event.event_date.strftime('%d %b %Y %H:%M')} · {event.status}",
        }
        for event in events
    ]
    if not rows:
        rows.append(
            {
                "id": "menu",
                "title": "Main Menu",
                "description": "No events found.",
            }
        )
    return [{"title": "Select event", "rows": rows}]


def _parse_finance_event_selection(message_text: str) -> str | None:
    text = (message_text or "").strip().lower()
    if not text.startswith(WHATSAPP_FINANCE_EVENT_ROW_PREFIX):
        return None
    return text[len(WHATSAPP_FINANCE_EVENT_ROW_PREFIX):].strip() or None


def _select_event_for_finance_action(*, db, sender_id: str, society_id, action: str) -> tuple[Event | None, bool]:
    latest_event = _get_latest_event_in_context(db=db, society_id=society_id)
    if latest_event and str((latest_event.status or "").upper()) in REPORT_AUTO_EVENT_STATES:
        return latest_event, True

    events = _recent_member_events(db=db, sender_id=sender_id)
    if len(events) == 1:
        return events[0], True
    return None, False


def _request_finance_event_selection(*, client, message, db, canonical_sender: str, action: str) -> bool:
    finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
    save_finance_action_session(
        finance_session_key,
        FinanceActionSessionState(pending_action=action, event_id=None),
    )
    events = _recent_member_events(db=db, sender_id=canonical_sender)
    client.send_list_message(
        to_phone=message.sender_id,
        header_text="Select Event",
        body_text="This action needs an event. Choose one to continue.",
        button_text="Choose Event",
        sections=_build_finance_event_sections(events),
    )
    return True

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


def _resolve_sender_society_context(*, db, sender_id: str, external_user_id: str):
    committee_member = _get_committee_member(
        db=db,
        sender_id=sender_id,
        external_user_id=external_user_id,
    )
    committee_society_id = getattr(committee_member, "society_id", None) if committee_member else None
    if committee_society_id:
        return committee_society_id, committee_member
    return resolve_sender_society_id(db, sender_id), committee_member if committee_member else None


def _is_registered_member_for_sender(*, db, sender_id: str) -> bool:
    normalized_sender = normalize_phone(sender_id)
    if not normalized_sender:
        return False

    candidate_ids = {normalized_sender}
    if len(normalized_sender) > 10:
        candidate_ids.add(normalized_sender[-10:])

    return (
        db.query(UserFlatMapping.id)
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(
            MemberIdentity.normalized_identifier.in_(tuple(candidate_ids)),
            UserFlatMapping.is_active.is_(True),
        )
        .first()
        is not None
    )


def _filter_sections_by_state(*, sections: list[dict], event_state: str | None, is_committee: bool) -> list[dict]:
    keyword_to_intent = {keyword: intent for intent, keyword in WHATSAPP_INTENTS.items()}
    filtered_sections = []
    for section in sections:
        rows = []
        for row in section.get("rows", []):
            row_id = (row.get("id") or "").strip().lower()
            intent = keyword_to_intent.get(row_id)
            if intent and not is_member_action_visible(intent=intent, event_state=event_state, is_committee=is_committee):
                continue
            rows.append(row)
        if rows:
            filtered_sections.append({**section, "rows": rows})
    return filtered_sections




def _with_navigation(
    *,
    sections: list[dict],
    back_id: str | None = None,
    include_main_menu: bool = True,
) -> list[dict]:
    nav_rows = []
    if back_id:
        nav_rows.append({"id": back_id, "title": "Back", "description": "Go to previous menu"})
    if include_main_menu:
        nav_rows.append({"id": "menu", "title": "Main Menu", "description": "Go to main menu"})
    return [*sections, {"title": "Navigation", "rows": nav_rows}] if nav_rows else sections


def _get_current_event_state(db, society_id) -> str | None:
    try:
        return get_event_state(_get_latest_event_in_context(db=db, society_id=society_id))
    except Exception:
        return None


def _button_row(row_id: str, title: str) -> dict:
    return {
        "type": "reply",
        "reply": {
            "id": row_id,
            "title": title[:20],
        },
    }


def _send_dashboard_ui(*, client, sender_id: str, is_committee: bool) -> None:
    if is_committee:
        buttons = [
            _button_row("ui::administration", "Administration"),
            _button_row("ui::reports", "Reports"),
            _button_row("ui::menu:more", "More"),
        ]
    else:
        buttons = [
            _button_row("ui::my-account", "My Account"),
            _button_row("ui::finance", "Finance"),
            _button_row("ui::menu:more", "More"),
        ]

    client.send_button_message(
        to_phone=sender_id,
        header_text="Society Control Panel",
        body_text="Select an action",
        buttons=buttons,
    )


def _send_dashboard_all_sections(*, client, sender_id: str, is_committee: bool) -> None:
    client.send_list_message(
        to_phone=sender_id,
        header_text="Society Control Panel",
        body_text="All available sections",
        button_text="Open",
        sections=_with_navigation(sections=build_main_dashboard_sections(is_committee=is_committee), back_id="ui::menu"),
    )



from app.channels.whatsapp.approval_flow import _send_approval_selection_list


def _try_handle_ui_message(*, client, message) -> bool:
    msg = message.text.strip().lower()

    canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
    membership_gated_ui_ids = {
        "ui::menu",
        "ui::menu:more",
        "ui::my-account",
        "ui::society",
        "ui::finance",
        "ui::payments",
        "ui::participation",
        "ui::reports",
        "ui::administration",
        "ui::administration:approvals",
        "ui::administration:operations",
        "ui::administration:operations:more",
        "ui::administration:reports",
    }
    if msg in membership_gated_ui_ids or msg in {"menu", "help"}:
        db = SessionLocal()
        try:
            try:
                society_id, committee_member = _resolve_sender_society_context(
                    db=db,
                    sender_id=canonical_sender,
                    external_user_id=message.sender_id,
                )
                latest_event = _get_latest_event_in_context(db=db, society_id=society_id)
                is_committee = committee_member is not None
                is_society_member = False
                if not is_committee:
                    is_society_member = _is_registered_member_for_sender(
                        db=db,
                        sender_id=canonical_sender,
                    )
                if latest_event and not is_committee and not is_society_member:
                    try:
                        resolve_flat(
                            db,
                            phone_number=canonical_sender,
                            society_id=latest_event.society_id,
                        )
                        is_society_member = True
                    except Exception:
                        try:
                            ensure_member_of_society(canonical_sender, db, latest_event.society_id)
                            is_society_member = True
                        except Exception:
                            is_society_member = False

                if not is_committee and not is_society_member:
                    client.send_button_message(
                        to_phone=message.sender_id,
                        header_text="Registration Required",
                        body_text="You are not registered yet. Tap below to join your society.",
                        buttons=[_button_row("ui::join-society", "Join Society")],
                    )
                    return True
            except Exception:
                logger.exception("Failed pre-check for WhatsApp UI registration gate")
        finally:
            db.close()

    if msg in {"menu", "help", "ui::menu", "ui::menu:more"}:
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(
                db=db,
                sender_id=canonical_sender,
                external_user_id=message.sender_id,
            )
            latest_event = _get_latest_event_in_context(db=db, society_id=society_id)
            is_committee = committee_member is not None
            is_society_member = False
            if latest_event and not is_committee:
                try:
                    resolve_flat(
                        db,
                        phone_number=canonical_sender,
                        society_id=latest_event.society_id,
                    )
                    is_society_member = True
                except Exception:
                    try:
                        ensure_member_of_society(canonical_sender, db, latest_event.society_id)
                        is_society_member = True
                    except Exception:
                        is_society_member = False

            requires_event_context = msg == "ui::menu:more"
            if requires_event_context and not latest_event:
                _send_dashboard_all_sections(
                    client=client,
                    sender_id=message.sender_id,
                    is_committee=False,
                )
                return True

            if msg == "ui::menu:more":
                _send_dashboard_all_sections(
                    client=client,
                    sender_id=message.sender_id,
                    is_committee=is_committee,
                )
                return True

            _send_dashboard_ui(
                client=client,
                sender_id=message.sender_id,
                is_committee=is_committee,
            )
            return True
        finally:
            db.close()

    if msg == "ui::participation":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            can_add_pass = is_member_action_visible(intent="ADD_PASS", event_state=event_state, is_committee=is_committee)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Participation",
                body_text="Participation",
                button_text="Open",
                sections=_with_navigation(sections=build_participation_sections(include_add_pass=can_add_pass), back_id="ui::my-account"),
            )
            return True
        finally:
            db.close()

    if msg == "ui::participation:add-update-pass":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            if not is_member_action_visible(intent="ADD_PASS", event_state=event_state, is_committee=is_committee):
                client.send_text_message(message.sender_id, "Pass updates are available only when event is active.")
                return True
        finally:
            db.close()
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="ADD_PASS_COUNTS"),
        )
        client.send_text_message(message.sender_id, add_or_update_pass_prompt())
        return True

    if msg == "ui::payments":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="Your Financial Overview",
            body_text="Select an action",
            button_text="Open",
            sections=_with_navigation(sections=build_payments_sections(), back_id="ui::finance"),
        )
        return True

    if msg == "ui::finance:view-balance":
        db = SessionLocal()
        try:
            finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
            finance_session = get_finance_action_session(finance_session_key)
            society_id, _committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            selected_event = None
            if finance_session and finance_session.pending_action == "VIEW_BALANCE" and finance_session.event_id:
                selected_event = db.query(Event).filter(Event.id == finance_session.event_id).first()
            if not selected_event:
                selected_event, _ = _select_event_for_finance_action(
                    db=db,
                    sender_id=canonical_sender,
                    society_id=society_id,
                    action="VIEW_BALANCE",
                )
            if not selected_event:
                return _request_finance_event_selection(
                    client=client,
                    message=message,
                    db=db,
                    canonical_sender=canonical_sender,
                    action="VIEW_BALANCE",
                )
            flat = resolve_flat(db, phone_number=canonical_sender, society_id=selected_event.society_id)
            balance = UserQueryService.get_my_balance(db=db, event_id=selected_event.id, flat_id=flat.id)
            summary = UserQueryService.get_my_payment_summary(db=db, event_id=selected_event.id, flat_id=flat.id)
            client.send_text_message(
                message.sender_id,
                format_financial_overview(
                    expected=format_currency(balance["expected"]),
                    paid=format_currency(balance["paid"]),
                    refunded=format_currency(summary["refunded"]),
                    outstanding=format_currency(balance["balance"]),
                ),
            )
            if finance_session and finance_session.pending_action == "VIEW_BALANCE":
                clear_finance_action_session(finance_session_key)
            return True
        except Exception:
            logger.exception("Failed to build financial overview")
            return False
        finally:
            db.close()

    if msg == "ui::make-payment":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
            finance_session = get_finance_action_session(finance_session_key)
            selected_event = None
            if finance_session and finance_session.pending_action == "MAKE_PAYMENT" and finance_session.event_id:
                selected_event = db.query(Event).filter(Event.id == finance_session.event_id).first()
            if not selected_event:
                selected_event, _ = _select_event_for_finance_action(
                    db=db,
                    sender_id=canonical_sender,
                    society_id=society_id,
                    action="MAKE_PAYMENT",
                )
            if not selected_event:
                return _request_finance_event_selection(
                    client=client,
                    message=message,
                    db=db,
                    canonical_sender=canonical_sender,
                    action="MAKE_PAYMENT",
                )
            flat = resolve_flat(db, phone_number=canonical_sender, society_id=selected_event.society_id)
            balance = UserQueryService.get_my_balance(db=db, event_id=selected_event.id, flat_id=flat.id)
            outstanding = balance.get("balance", 0)
            if outstanding <= 0:
                client.send_text_message(message.sender_id, "No outstanding balance to pay.")
                return True
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Make Payment",
                body_text=f"Outstanding Amount: {format_currency(outstanding)}",
                button_text="Choose",
                sections=build_make_payment_sections(outstanding_amount=str(int(outstanding) if float(outstanding).is_integer() else outstanding)),
            )
            if finance_session and finance_session.pending_action == "MAKE_PAYMENT":
                clear_finance_action_session(finance_session_key)
            return True
        except Exception:
            logger.exception("Failed to build make payment menu")
            return False
        finally:
            db.close()

    if msg == "ui::finance:pay-custom":
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="PAY_CUSTOM"),
        )
        client.send_text_message(message.sender_id, payment_custom_amount_prompt())
        return True

    if msg == "ui::request-refund":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            if not is_member_action_visible(intent="REFUND", event_state=event_state, is_committee=is_committee):
                client.send_text_message(message.sender_id, "Payment and refund requests are available only when event is active.")
                return True
        finally:
            db.close()
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="REFUND_REQUEST"),
        )
        client.send_text_message(message.sender_id, refund_request_prompt())
        return True

    if msg == "ui::my-account":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="My Account",
            body_text="Select an action",
            button_text="Open",
            sections=_with_navigation(sections=build_my_account_sections(), back_id="ui::menu"),
        )
        return True

    if msg == "ui::society":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="Society",
            body_text="Select an action",
            button_text="Open",
            sections=_with_navigation(sections=build_society_sections(), back_id="ui::menu"),
        )
        return True

    if msg == "ui::join-society":
        session_key = build_join_session_key(sender_id=message.sender_id)
        save_join_session(
            session_key,
            JoinSessionState(pending_action="JOIN"),
        )
        client.send_text_message(message.sender_id, "Please enter join code")
        return True

    if msg == "ui::finance":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            can_use_payment = is_member_action_visible(intent="PAY", event_state=event_state, is_committee=is_committee)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Finance",
                body_text="Select an action",
                button_text="Open",
                sections=_with_navigation(sections=build_finance_sections(include_payment_actions=can_use_payment), back_id="ui::menu"),
            )
            return True
        finally:
            db.close()

    if msg == "ui::reports":
        db = SessionLocal()
        try:
            _society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            sections = build_reports_sections(is_committee=is_committee)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Reports",
                body_text="Select a report action",
                button_text="Open",
                sections=_with_navigation(sections=sections, back_id="ui::menu"),
            )
            return True
        finally:
            db.close()

    if msg in {"ui::administration", "ui::administration:approvals", "ui::administration:operations", "ui::administration:operations:more", "ui::administration:reports"}:
        db = SessionLocal()
        try:
            member = _get_committee_member(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            if not member:
                client.send_text_message(message.sender_id, "Access restricted.")
                return True
            if msg == "ui::administration:approvals":
                base_sections = build_committee_approvals_sections()
                back_id = "ui::administration"
                body_text = "Approval actions"
            elif msg == "ui::administration:operations":
                base_sections = build_committee_operations_sections()
                back_id = "ui::administration"
                body_text = "Operational actions"
            elif msg == "ui::administration:operations:more":
                base_sections = build_committee_operations_more_sections()
                back_id = "ui::administration:operations"
                body_text = "More operational actions"
            elif msg == "ui::administration:reports":
                base_sections = build_committee_reports_sections()
                back_id = "ui::administration"
                body_text = "Report actions"
            else:
                base_sections = build_committee_sections()
                back_id = "ui::menu"
                body_text = "Select an area"

            sections = base_sections
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Administration",
                body_text=body_text,
                button_text="Open",
                sections=_with_navigation(
                    sections=sections,
                    back_id=back_id,
                    include_main_menu=True,

                ),
            )
            return True
        finally:
            db.close()


    if msg == "ui::approve-user":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            return _send_approval_selection_list(
                client=client,
                sender_id=message.sender_id,
                approval_type="user",
                db=db,
                canonical_sender=canonical_sender,
                external_user_id=message.sender_id,
            )
        finally:
            db.close()

    if msg == "ui::approve-payment":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            return _send_approval_selection_list(
                client=client,
                sender_id=message.sender_id,
                approval_type="payment",
                db=db,
                canonical_sender=canonical_sender,
                external_user_id=message.sender_id,
            )
        finally:
            db.close()

    if msg == "ui::approve-refund":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            return _send_approval_selection_list(
                client=client,
                sender_id=message.sender_id,
                approval_type="refund",
                db=db,
                canonical_sender=canonical_sender,
                external_user_id=message.sender_id,
            )
        finally:
            db.close()

    return False

