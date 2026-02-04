#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:33:10 2026

@author: anonymous
"""

# app/whatsapp/handlers/committee_handler.py

from sqlalchemy import func

from app.db.models import Flat, Payment, Refund, EventFoodPass
from app.modules.expenses.expense_service import ExpenseService
from app.modules.onboarding.admin_approval_service import AdminApprovalService
from app.modules.onboarding.admin_query_service import AdminOnboardingQueryService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.modules.reports.pending_payment_report import PendingPaymentReport
from app.modules.reports.event_participation_report import EventParticipationReport
from app.permissions.guard import is_action_allowed
from app.utils.response import success, error, warning
from app.whatsapp.parser import parse_amount


def handle_committee_intent(
    *,
    db,
    intent,
    message,
    event,
    member
):
    if intent == "ADD_EXPENSE":
        if not is_action_allowed(member.role, "ADD_EXPENSE"):
            return warning(
                "This action normally requires Secretary approval. "
                "Please ask Chairman to override."
            )

        if not event:
            return error("No active event found. Please contact committee.")

        amount = parse_amount(message)
        if not amount:
            return error("Please specify amount. Example: expense water 1200")

        reason = message.replace(str(amount), "").strip()

        ExpenseService.add_expense(
            db=db,
            event_id=event.id,
            description=reason or "WhatsApp expense",
            amount=amount,
            performed_by=member.id,
            override_reason="Via WhatsApp"
        )
        return success(f"🧾 Expense added: ₹{amount}")

    if intent == "PENDING_PAYMENTS":
        if not is_action_allowed(member.role, "PAY"):
            return warning(
                "This action normally requires Treasurer approval."
            )

        if not event:
            return error("No active event found. Please contact committee.")

        pending = PendingPaymentReport.get_pending_flats(
            db=db,
            event_id=event.id,
            society_id=event.society_id
        )

        if not pending:
            return success("🎉 All flats have completed payments.")

        lines = ["⏳ *Pending Payments*"]
        for p in pending:
            lines.append(
                f"{p['flat']} – Pending ₹{p['pending']}"
            )

        return success("\n".join(lines))

    if intent == "PARTICIPATION_REPORT":
        if not event:
            return error("No active event found. Please contact committee.")

        report = EventParticipationReport.generate(
            db=db,
            event_id=event.id,
            society_id=event.society_id
        )

        participating = report["participating"]
        not_participating = report["not_participating"]

        lines = [
            f"🎫 *Participation Report* ({event.name})",
            "",
            "*Joined*:",
            ", ".join(participating) if participating else "None",
            "",
            "*Not Joined*:",
            ", ".join(not_participating) if not_participating else "None"
        ]
        return success("\n".join(lines))

    if intent == "REMIND_FLAT":
        if not is_action_allowed(member.role, "PAY"):
            return warning(
                "This action normally requires Treasurer approval."
            )

        if not event:
            return error("No active event found. Please contact committee.")

        parts = message.split()
        if len(parts) < 2:
            return error("Example: remind A-101")

        flat_number = parts[1]

        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == event.society_id
            )
            .first()
        )

        if not flat:
            return error("Flat not found.")

        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event.id,
                EventFoodPass.flat_id == flat.id,
                EventFoodPass.is_participating.is_(True)
            )
            .first()
        )

        if not food_pass:
            return error("Flat has not joined the event.")

        paid_amount = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(
                Payment.event_id == event.id,
                Payment.flat_id == flat.id
            )
            .scalar()
        )

        refunded_amount = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(
                Refund.event_id == event.id,
                Refund.flat_id == flat.id,
                Refund.status == "refunded"
            )
            .scalar()
        )

        pending_amount = food_pass.total_amount - paid_amount - refunded_amount
        if pending_amount <= 0:
            return success(f"{flat_number} has no pending payment.")

        return success(
            f"📢 *Payment Reminder*\n\n"
            f"Dear {flat_number},\n"
            f"Your pending amount for *{event.name}* is ₹{pending_amount}.\n"
            f"Please pay at your convenience.\n\n"
            f"Thank you."
        )

    if intent == "APPROVE":
        if not is_action_allowed(member.role, "ALL"):
            return warning("Only Chairman can approve users.")

        parts = message.split()
        if len(parts) < 3:
            return error("Example: approve user REQ-003")

        request_code = parts[2].upper()

        AdminApprovalService.approve_user(
            db=db,
            society_id=event.society_id,
            request_code=request_code
        )

        return success(f"✅ User approved ({request_code})")

    if intent == "APPROVE_PAYMENT":
        if not is_action_allowed(member.role, "PAY"):
            return warning("Only Treasurer can approve payments.")

        parts = message.split()
        if len(parts) < 3:
            return error("Example: approve payment PAY-001")

        request_code = parts[2].upper()
        request = PaymentRequestService.get_request_by_code(
            db=db,
            request_code=request_code
        )
        if not request:
            return error("Payment request not found.")
        if request.status != "requested":
            return warning("Payment request already processed.")

        PaymentRequestService.approve_request(
            db=db,
            request=request,
            performed_by=member.id
        )
        return success(f"✅ Payment approved ({request_code})")

    if intent == "APPROVE_REFUND":
        if not is_action_allowed(member.role, "REFUND"):
            return warning("Only Treasurer can approve refunds.")

        parts = message.split()
        if len(parts) < 3:
            return error("Example: approve refund REF-001")

        request_code = parts[2].upper()
        request = RefundRequestService.get_request_by_code(
            db=db,
            request_code=request_code
        )
        if not request:
            return error("Refund request not found.")
        if request.status != "requested":
            return warning("Refund request already processed.")

        RefundRequestService.approve_request(
            db=db,
            request=request,
            performed_by=member.id
        )
        return success(f"✅ Refund approved ({request_code})")

    if intent == "PENDING_USERS":
        if not is_action_allowed(member.role, "ALL"):
            return warning("Only Chairman can view pending users.")

        latest_event = event
        if not latest_event:
            return error("No society context found.")

        society_id = latest_event.society_id

        pending = AdminOnboardingQueryService.list_pending_users(
            db=db,
            society_id=society_id
        )

        if not pending:
            return success("🎉 No pending user requests.")

        lines = ["⏳ *Pending Join Requests*"]
        for p in pending:
            lines.append(
                f"Request: *{p.request_code}*\n"
                f"Flat: {p.flat_number}\n"
                f"Requested At: {p.created_at.strftime('%d %b %Y %H:%M')}\n"
                f"---"
            )

        return success("\n".join(lines))

    return None
