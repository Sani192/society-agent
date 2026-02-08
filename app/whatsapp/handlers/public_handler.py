#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:30:44 2026

@author: anonymous
"""

# app/whatsapp/handlers/public_handler.py

from app.modules.events.food_pass_service import FoodPassService
from app.modules.payments.payment_service import PaymentService
from app.modules.payments.refund_service import RefundService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.modules.reports.block.block_contribution_service import BlockContributionReport
from app.modules.reports.public.public_event_summary_report import PublicEventSummaryReport
from app.db.models import AuditLog
from app.modules.users.user_query_service import UserQueryService
from app.utils.logger import logger
from app.utils.response import success, error
from app.whatsapp.parser import parse_amount, parse_pass_counts, parse_reason, parse_target_flat
from app.whatsapp.handlers.common import resolve_flat


def _resolve_member_flat(db, *, phone_number, event):
    try:
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id
        )
    except Exception as exc:
        return None, error(str(exc))

    return flat, None


def handle_public_intent(
    *,
    db,
    intent,
    phone_number,
    message,
    event,
    member
):
    allow_delegate = member is not None

    if intent == "ADD_PASS":
        if not event:
            return error("No active event found. Please contact committee.")

        flat_number = parse_target_flat(message) if allow_delegate else None
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id,
            flat_number=flat_number
        )

        counts = parse_pass_counts(message)
        if sum(counts.values()) == 0:
            return error("Specify counts. Example: add pass veg 2 jain 1 kid 1")

        FoodPassService.add_or_update_pass(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            veg_count=counts["veg"],
            jain_count=counts["jain"],
            kids_count=counts["kids"],
            charge_per_person=300,
            performed_by=member.id if member else None,
            override_reason="Via WhatsApp" if member else "Self service via WhatsApp"
        )

        return success(
            f"✅ Pass updated: veg {counts['veg']}, jain {counts['jain']}, kids {counts['kids']}"
        )

    if intent == "PAY":
        if not event:
            return error("No active event found. Please contact committee.")

        flat_number = parse_target_flat(message) if allow_delegate else None
        flat = resolve_flat(
            db,
            phone_number=phone_number,
            society_id=event.society_id,
            flat_number=flat_number
        )

        amount = parse_amount(message)
        if not amount:
            return error("Please specify amount. Example: pay 500")

        if not member:
            request = PaymentRequestService.request_payment(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                amount=amount,
                payment_mode="upi",
                requested_by=phone_number
            )
            return success(
                "⏳ Payment request sent for treasurer approval.\n"
                f"Request ID: *{request.request_code}*"
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
            return success(
                f"✅ Payment approved and recorded (Request {request.request_code})"
            )

        PaymentService.record_payment(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            amount=amount,
            payment_mode="upi",
            performed_by=member.id,
            override_reason="Via WhatsApp"
        )
        return success(f"💰 Payment received: ₹{amount}")

    if intent == "REFUND":
        if not event:
            return error("No active event found. Please contact committee.")

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
            return error("Example: refund 200 reason guest absent")

        if not member:
            request = RefundRequestService.request_refund(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                amount=amount,
                reason=reason,
                requested_by=phone_number
            )
            return success(
                "⏳ Refund request sent for treasurer approval.\n"
                f"Request ID: *{request.request_code}*"
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
            return success(
                f"✅ Refund approved and processed (Request {request.request_code})"
            )

        RefundService.process_refund(
            db=db,
            event_id=event.id,
            flat_id=flat.id,
            amount=amount,
            performed_by=member.id,
            reason=reason,
            override_reason="Via WhatsApp"
        )

        return success(f"↩️ Refund processed: ₹{amount}")

    if intent == "MY_PASS":
        if not event:
            return error("No active event found. Please contact committee.")

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
            return success("🎫 You have not taken a food pass for this event.")

        return success(
            f"🎫 Your Food Pass\n"
            f"Veg: {food_pass.veg_count}\n"
            f"Jain: {food_pass.jain_count}\n"
            f"Kids: {food_pass.kids_count}"
        )

    if intent == "MY_PAYMENT_REQUESTS":
        if not event:
            return error("No active event found. Please contact committee.")

        flat, error_response = _resolve_member_flat(
            db,
            phone_number=phone_number,
            event=event
        )
        if error_response:
            return error_response

        requests = PaymentRequestService.list_requests(
            db=db,
            event_id=event.id,
            requested_by=phone_number
        )

        if not requests:
            return success("✅ No payment requests found.")

        lines = ["📥 *Your Payment Requests*"]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | ₹{request.amount} | "
                f"{request.status}"
            )

        return success("\n".join(lines))

    if intent == "MY_REFUND_REQUESTS":
        if not event:
            return error("No active event found. Please contact committee.")

        flat, error_response = _resolve_member_flat(
            db,
            phone_number=phone_number,
            event=event
        )
        if error_response:
            return error_response

        requests = RefundRequestService.list_requests(
            db=db,
            event_id=event.id,
            requested_by=phone_number
        )

        if not requests:
            return success("✅ No refund requests found.")

        lines = ["📤 *Your Refund Requests*"]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | ₹{request.amount} | "
                f"{request.status}"
            )

        return success("\n".join(lines))

    if intent == "MY_PAYMENTS":
        if not event:
            return error("No active event found. Please contact committee.")

        flat, error_response = _resolve_member_flat(
            db,
            phone_number=phone_number,
            event=event
        )
        if error_response:
            return error_response

        summary = UserQueryService.get_my_payment_summary(
            db=db,
            event_id=event.id,
            flat_id=flat.id
        )

        requests = PaymentRequestService.list_requests(
            db=db,
            event_id=event.id,
            requested_by=phone_number,
            status="approved"
        )

        header = (
            f"💰 Payment Summary\n"
            f"Paid: ₹{summary['paid']}\n"
            f"Refunded: ₹{summary['refunded']}\n"
            f"Net Paid: ₹{summary['net_paid']}"
        )

        if not requests:
            return success(
                f"{header}\n\n"
                "✅ No approved payments found for this event."
            )

        lines = [header, "", "💰 *Your Payments*"]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | ₹{request.amount} | "
                f"approved"
            )

        return success("\n".join(lines))

    if intent == "MY_BALANCE":
        if not event:
            return error("No active event found. Please contact committee.")

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

        return success(
            f"📊 Your Balance\n"
            f"Expected: ₹{balance['expected']}\n"
            f"Paid: ₹{balance['paid']}\n"
            f"Remaining: ₹{balance['balance']}"
        )

    if intent == "MY_STATUS":
        if not event:
            return error("No active event found. Please contact committee.")

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

        return success(f"📌 Event Status: {status}")

    if intent == "SUMMARY":
        if not event:
            return error("No active event found. Please contact committee.")

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
            "📊 *Event Summary*",
            f"Participants: {summary['participants']}",
            f"Total Income: ₹{summary['income']}",
            f"Total Expenses: ₹{summary['expenses']}",
            f"Closing Balance: ₹{summary['closing_balance']}"
        ]

        if summary["sponsors"]:
            lines.append(f"Sponsors: {', '.join(summary['sponsors'])}")

        return success("\n".join(lines))

    if intent == "BLOCK_REPORT":
        if not event:
            return error("No active event found. Please contact committee.")

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
            return success("🏢 No block contributions recorded yet.")

        lines = ["🏢 *Block Contribution Report*"]
        for block, amount in report.items():
            lines.append(f"{block}: ₹{amount}")

        return success("\n".join(lines))

    if intent == "HELP":
        return success(
            "🤖 *Society Assistant Help*\n\n"
            "You can manage event participation, payments and view details.\n\n"
            "Type *commands* to see everything you can do."
        )

    if intent == "COMMANDS":
        return success(
            "📋 *Available Commands*\n\n"
            "🎫 *Participation*\n"
            "- add pass veg 2 jain 1\n"
            "- add pass veg 2 jain 1 for A-101 (committee)\n"
            "- my pass\n"
            "- my status\n\n"
            "🏠 *Join Society*\n"
            "- join ABC123 A-101\n"
            "- join ABC123 A-101 phone 9876543210 (committee)\n"
            "- join status\n"
            "- join status phone 9876543210 (committee)\n\n"
            "💰 *Payments*\n"
            "- pay 500\n"
            "- pay 500 for A-101 (committee)\n"
            "- my payments\n"
            "- my payment requests\n"
            "- my balance\n\n"
            "↩️ *Refunds*\n"
            "- refund 200 reason guest absent\n"
            "- refund 200 reason guest absent for A-101 (committee)\n"
            "- my refund requests\n\n"
            "🧾 *Expenses* (Committee)\n"
            "- expense water tanker 1200\n\n"
            "📊 *Reports* (Committee)\n"
            "- participation report\n"
            "- pending payments\n\n"
            "📈 *Group-safe Reports*\n"
            "- summary\n"
            "- block report\n\n"
            "✅ *Approvals* (Treasurer)\n"
            "- approve payment PAY-001\n"
            "- approve refund REF-001\n"
            "- payment requests\n"
            "- refund requests\n\n"
            "ℹ️ *Help*\n"
            "- help\n"
            "- commands"
        )

    return None
