#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:30:44 2026

@author: anonymous
"""

# app/whatsapp/handlers/public_handler.py

from app.modules.events.food_pass_service import FoodPassService
from app.modules.events.food_collection_service import FoodCollectionService
from app.modules.payments.payment_service import PaymentService
from app.modules.payments.refund_service import RefundService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.modules.reports.block.block_contribution_service import BlockContributionReport
from app.modules.reports.public.public_event_summary_report import PublicEventSummaryReport
from app.db.models import AuditLog, Payment
from app.modules.users.user_query_service import UserQueryService
from app.utils.logger import logger
from app.channels.whatsapp.response_templates import (
    error_response,
    format_currency,
    format_heading,
    join_lines,
    success_response,
)
from app.commands.parser import parse_amount, parse_pass_counts, parse_reason, parse_target_flat
from app.handlers.shared.common import resolve_flat
from app.i18n.catalog import translate
from app.utils.guards import ensure_member_of_society
from app.permissions.command_policy import get_event_state, member_action_state_warning
from app.utils.response import safe_error_message


def _resolve_member_flat(db, *, phone_number, event):
    try:
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id
        )
    except Exception as exc:
        logger.warning("Failed to resolve member flat", exc_info=exc)
        return None, error_response("Unable to resolve your flat for this event.")

    return flat, None

def _resolve_requester_mappings(db, *, phone_number, event):
    return ensure_member_of_society(
        phone_number=phone_number,
        db=db,
        society_id=event.society_id
    )


def _pick_requester_mapping_id(mappings, flat_id):
    for mapping in mappings:
        if mapping.flat_id == flat_id:
            return mapping.id
    return mappings[0].id


def _format_by_type_summary(summary):
    by_type = summary.get("by_type", {})
    if not by_type:
        return []

    label_map = {
        "veg": "Veg",
        "jain": "Jain",
        "kids": "Kids",
    }

    lines = []
    for food_type, counts in by_type.items():
        label = label_map.get(food_type.lower(), food_type.replace("_", " ").title())
        lines.append(
            f"{label}: served {counts['served']} / total {counts['total']} (remaining {counts['remaining']})"
        )
    return lines

def handle_public_intent(
    *,
    db,
    intent,
    phone_number,
    message,
    event,
    member,
    lang: str | None = None,
    trace_id: str | None = None,
    correlation_id: str | None = None,
):
    allow_delegate = member is not None
    event_state = get_event_state(event)

    blocked_message = member_action_state_warning(intent=intent, event_state=event_state)
    if blocked_message and not allow_delegate:
        return error_response(blocked_message)

    if intent == "ADD_PASS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat_number = parse_target_flat(message) if allow_delegate else None
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id,
            flat_number=flat_number
        )

        counts = parse_pass_counts(message)
        if sum(counts.values()) == 0:
            return error_response(translate("public.add_pass.specify_counts", lang))

        charge_per_adult = event.charge_per_adult
        charge_per_child = event.charge_per_child
        if charge_per_adult is None or charge_per_child is None:
            return error_response(
                translate("public.add_pass.pricing_missing", lang)
            )

        FoodPassService.add_or_update_pass(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            veg_count=counts["veg"],
            jain_count=counts["jain"],
            kids_count=counts["kids"],
            charge_per_adult=charge_per_adult,
            charge_per_child=charge_per_child,
            performed_by=member.id if member else None,
            override_reason="Via WhatsApp" if member else None
        )

        return success_response(
            join_lines([
                translate("public.common.veg_count", lang, count=counts["veg"]),
                translate("public.common.jain_count", lang, count=counts["jain"]),
                translate("public.common.kids_count", lang, count=counts["kids"]),
            ]),
            heading=translate("public.add_pass.heading", lang),
            emoji="🎫"
        )

    if intent == "PAY":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat_number = parse_target_flat(message) if allow_delegate else None
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id,
            flat_number=flat_number
        )

        amount = parse_amount(message)
        if not amount:
            return error_response(translate("public.pay.specify_amount", lang))

        if not member:
            mappings = _resolve_requester_mappings(db, phone_number=phone_number, event=event)
            request = PaymentRequestService.request_payment(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                amount=amount,
                payment_mode="upi",
                requested_by_mapping_id=_pick_requester_mapping_id(mappings, flat.id)
            )
            return success_response(
                join_lines([
                    translate("public.pay.request_sent", lang),
                    translate("public.common.request_id_line", lang, request_id=request.request_code)
                ]),
                heading=translate("public.pay.request_submitted_heading", lang),
                emoji="⏳"
            )

        request = PaymentRequestService.find_matching_request(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            amount=amount
        )
        if request:
            PaymentRequestService.approve_request(
                db=db,
                request=request,
                performed_by=member.id
            )
            return success_response(
                translate("public.pay.approved_and_recorded", lang, request_code=request.request_code)
            )

        PaymentService.record_payment(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            amount=amount,
            payment_mode="upi",
            performed_by=member.id,
            override_reason="Via WhatsApp",
            require_approved_request_context=True,
        )
        return success_response(
            translate("public.pay.payment_received", lang, amount=format_currency(amount))
        )

    if intent == "REFUND":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat_number = parse_target_flat(message) if allow_delegate else None
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id,
            flat_number=flat_number
        )

        amount = parse_amount(message)
        reason = parse_reason(message)

        if not amount or not reason:
            return error_response(translate("public.refund.example", lang))

        if not member:
            try:
                mappings = _resolve_requester_mappings(db, phone_number=phone_number, event=event)
                request = RefundRequestService.request_refund(
                    db=db,
                    event_id=event.id,
                    flat_id=flat.id,
                    amount=amount,
                    reason=reason,
                    requested_by_mapping_id=_pick_requester_mapping_id(mappings, flat.id)
                )
            except Exception as exc:
                logger.warning(
                    "Refund request failed",
                    exc_info=exc,
                    extra={"trace_id": trace_id, "correlation_id": correlation_id},
                )
                return error_response(safe_error_message(lang=lang))
            return success_response(
                join_lines([
                    translate("public.refund.request_sent", lang),
                    translate("public.common.request_id_line", lang, request_id=request.request_code)
                ]),
                heading=translate("public.refund.request_submitted_heading", lang),
                emoji="⏳"
            )

        request = RefundRequestService.find_matching_request(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            amount=amount
        )
        if request:
            RefundRequestService.approve_request(
                db=db,
                request=request,
                performed_by=member.id
            )
            return success_response(
                translate("public.refund.approved_and_processed", lang, request_code=request.request_code)
            )

        try:
            RefundService.process_refund(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                amount=amount,
                performed_by=member.id,
                reason=reason,
                override_reason="Via WhatsApp",
                require_approved_request_context=True,
            )
        except Exception as exc:
            logger.warning(
                "Refund processing failed",
                exc_info=exc,
                extra={"trace_id": trace_id, "correlation_id": correlation_id},
            )
            return error_response(safe_error_message(lang=lang))

        return success_response(
            translate("public.refund.processed", lang, amount=format_currency(amount))
        )

    if intent == "MY_PASS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id
        )

        food_pass = UserQueryService.get_my_pass(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        if not food_pass:
            return success_response(
                translate("public.my_pass.no_pass", lang),
                heading=translate("public.my_pass.no_pass_heading", lang),
                emoji="🎫"
            )

        summary = FoodCollectionService.member_pass_status(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
        )

        lines = [
            f"Veg: {food_pass.veg_count}",
            f"Jain: {food_pass.jain_count}",
            f"Kids: {food_pass.kids_count}",
        ]
        by_type_lines = _format_by_type_summary(summary)
        if by_type_lines:
            lines.extend(["", *by_type_lines])

        if summary["total_passes"] > 0:
            lines.extend([
                "",
                f"Total Plates: {summary['total_passes']}",
                f"Served: {summary['served']}",
                f"Remaining: {summary['remaining']}",
            ])
            if summary.get("fallback_served"):
                lines.append(translate("public.my_pass.fallback_served", lang, count=summary["fallback_served"]))
            lines.append(translate("public.my_pass.view_tokens_hint", lang))

        return success_response(join_lines(lines), heading=translate("public.my_pass.heading", lang), emoji="🎫")

    if intent == "MY_TOKENS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id,
        )
        summary = FoodCollectionService.member_pass_status(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
        )
        if not summary["tokens"]:
            return success_response(
                translate("public.my_tokens.not_generated", lang),
                heading=translate("public.my_tokens.heading", lang),
                emoji="🎟️",
            )

        token_lines = [
            (
                f"{row['token']} | {row['food_type']} | {'Served' if row['served'] else 'Pending'}"
                + (" | Fallback serve" if row.get('is_fallback') else "")
            )
            for row in summary["tokens"]
        ]
        by_type_lines = _format_by_type_summary(summary)

        summary_lines = [
            *by_type_lines,
            *( [""] if by_type_lines else []),
            f"Total: {summary['total_passes']}",
            f"Served: {summary['served']}",
            f"Remaining: {summary['remaining']}",
            *( [f"Fallback served (no-token): {summary['fallback_served']}"] if summary.get('fallback_served') else []),
            "",
            translate("public.my_tokens.tokens_label", lang),
            *token_lines,
        ]

        return success_response(
            join_lines(summary_lines),
            heading=translate("public.my_tokens.heading", lang),
            emoji="🎟️",
        )

    if intent == "MY_PAYMENT_REQUESTS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat, error_reply = _resolve_member_flat(
            db,
            phone_number=phone_number,
            event=event
        )
        if error_reply:
            return error_reply

        requests = PaymentRequestService.list_requests(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        if not requests:
            return success_response(
                translate("public.payment_requests.none", lang),
                heading=translate("public.payment_requests.heading", lang),
                emoji="📥"
            )

        lines = [format_heading(translate("public.payment_requests.heading", lang), "📥")]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | "
                f"{format_currency(request.amount)} | "
                f"{request.status}"
            )

        return success_response(join_lines(lines))

    if intent == "MY_REFUND_REQUESTS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat, error_reply = _resolve_member_flat(
            db,
            phone_number=phone_number,
            event=event
        )
        if error_reply:
            return error_reply

        requests = RefundRequestService.list_requests(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        if not requests:
            return success_response(
                translate("public.refund_requests.none", lang),
                heading=translate("public.refund_requests.heading", lang),
                emoji="📤"
            )

        lines = [format_heading(translate("public.refund_requests.heading", lang), "📤")]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | "
                f"{format_currency(request.amount)} | "
                f"{request.status}"
            )

        return success_response(join_lines(lines))

    if intent == "MY_PAYMENTS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat, error_reply = _resolve_member_flat(
            db,
            phone_number=phone_number,
            event=event
        )
        if error_reply:
            return error_reply

        summary = UserQueryService.get_my_payment_summary(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        balance = UserQueryService.get_my_balance(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event.id,
                Payment.flat_id == flat.id
            )
            .first()
        )

        payment_status = payment.status if payment else "pending"
        payment_paid = payment.paid_amount if payment else 0
        payment_expected = payment.expected_amount if payment else balance["expected"]

        requests = PaymentRequestService.list_requests(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        header = join_lines([
            format_heading(translate("public.my_payments.summary_heading", lang), "💰"),
            translate("public.my_payments.paid_line", lang, amount=format_currency(summary["paid"])),
            translate("public.my_payments.refunded_line", lang, amount=format_currency(summary["refunded"])),
            translate("public.my_payments.net_paid_line", lang, amount=format_currency(summary["net_paid"])),
            translate(
                "public.my_payments.status_line",
                lang,
                status=payment_status,
                paid=format_currency(payment_paid),
                expected=format_currency(payment_expected),
            ),
        ])

        if not requests:
            return success_response(
                join_lines([
                    header,
                    "",
                    translate("public.my_payments.none_for_event", lang),
                ])
            )

        lines = [header, "", format_heading(translate("public.payment_requests.heading", lang), "📥")]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | "
                f"{format_currency(request.amount)} | "
                f"{request.status}"
            )

        return success_response(join_lines(lines))

    if intent == "MY_BALANCE":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id
        )

        balance = UserQueryService.get_my_balance(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        return success_response(
            join_lines([
                translate("public.my_balance.expected_line", lang, amount=format_currency(balance["expected"])),
                translate("public.my_balance.paid_line", lang, amount=format_currency(balance["paid"])),
                translate("public.my_balance.remaining_line", lang, amount=format_currency(balance["balance"])),
            ]),
            heading=translate("public.my_balance.heading", lang),
            emoji="📊"
        )

    if intent == "MY_STATUS":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id
        )

        status = UserQueryService.get_my_status(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        return success_response(
            translate("public.my_status.event_status_line", lang, status=status),
            heading=translate("public.my_status.heading", lang),
            emoji="📌"
        )

    if intent == "SUMMARY":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        logger.info("Generating public event summary for event %s", event.id)
        summary = PublicEventSummaryReport.generate(
            db=db,
            event_id=event.id
        )
        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="report",
            entity_id=event.id,
            action="VIEW_EVENT_SUMMARY",
            reason="WhatsApp public summary",
            performed_by=member.id if member else None
        ))
        db.commit()

        lines = [
            format_heading(translate("public.summary.heading", lang), "📊"),
            translate("public.summary.participants_line", lang, count=summary["participants"]),
            translate("public.summary.total_income_line", lang, amount=format_currency(summary["income"])),
            translate("public.summary.total_expenses_line", lang, amount=format_currency(summary["expenses"])),
            translate("public.summary.closing_balance_line", lang, amount=format_currency(summary["closing_balance"])),
        ]

        if summary["sponsors"]:
            lines.append(f"Sponsors: {', '.join(summary['sponsors'])}")

        return success_response(join_lines(lines))

    if intent == "BLOCK_REPORT":
        if not event:
            return error_response(translate("public.common.no_active_event", lang))

        logger.info("Generating block contribution report for event %s", event.id)
        report = BlockContributionReport.generate(
            db=db,
            event_id=event.id
        )
        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="report",
            entity_id=event.id,
            action="VIEW_BLOCK_REPORT",
            reason="WhatsApp block report",
            performed_by=member.id if member else None
        ))
        db.commit()

        if not report:
            return success_response(
                translate("public.block_report.none", lang),
                heading=translate("public.block_report.heading", lang),
                emoji="🏢"
            )

        lines = [format_heading(translate("public.block_report.heading", lang), "🏢")]
        for block, amount in report.items():
            lines.append(f"{block}: {format_currency(amount)}")

        return success_response(join_lines(lines))

    if intent == "MENU":
        return success_response(
            join_lines([
                translate("public.menu.title_line", lang),
                translate("public.menu.status_line", lang),
                translate("public.menu.balance_line", lang),
                translate("public.menu.payments_line", lang),
                translate("public.menu.pass_line", lang),
                translate("public.menu.help_line", lang),
            ]),
            heading=translate("public.menu.heading", lang),
            emoji="📋",
        )

    if intent == "HELP":
        return success_response(
            join_lines([
                translate("public.help.menu_hint", lang),
                translate("public.help.onboarding_hint", lang),
                translate("public.help.support_hint", lang),
            ]),
            heading=translate("public.help.heading", lang),
        )

    return None
