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
from app.modules.contributions.contribution_service import ContributionService
from app.modules.contributions.contribution_refund_service import ContributionRefundService
from app.modules.reports.pending_payment_report import PendingPaymentReport
from app.modules.reports.event_participation_report import EventParticipationReport
from app.permissions.guard import is_action_allowed
from app.utils.response import success, error, warning
from app.whatsapp.parser import parse_amount, parse_reason


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

    if intent == "PAYMENT_REQUESTS":
        if not is_action_allowed(member.role, "PAY"):
            return warning("Only Treasurer can view payment requests.")

        if not event:
            return error("No active event found. Please contact committee.")

        requests = PaymentRequestService.list_requests(
            db=db,
            event_id=event.id
        )

        if not requests:
            return success("✅ No payment requests found.")

        lines = ["📥 *Payment Requests*"]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | ₹{request.amount} | "
                f"{request.requested_by} | {request.status}"
            )

        return success("\n".join(lines))

    if intent == "REFUND_REQUESTS":
        if not is_action_allowed(member.role, "REFUND"):
            return warning("Only Treasurer can view refund requests.")

        if not event:
            return error("No active event found. Please contact committee.")

        requests = RefundRequestService.list_requests(
            db=db,
            event_id=event.id
        )

        if not requests:
            return success("✅ No refund requests found.")

        lines = ["📤 *Refund Requests*"]
        for request, flat in requests:
            lines.append(
                f"{request.request_code} | {flat.flat_number} | ₹{request.amount} | "
                f"{request.requested_by} | {request.status}"
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
    
    if intent == "ADD_SPONSOR":
        if not is_action_allowed(member.role, "ADD_SPONSOR"):
            return warning("Only committee members can add sponsors.")
    
        raw = message.replace("add sponsor", "", 1).strip()
    
        if not raw:
            return error("Example: add sponsor Shree Caterers 10000")
    
        flat_id = None
    
        # ------------------------------------------------
        # IN-KIND SPONSOR (name + in-kind + details)
        # ------------------------------------------------
        if "in-kind" in raw:
            before, after = raw.split("in-kind", 1)
    
            sponsor_name = before.strip()
            details = after.strip()
    
            if not sponsor_name or not details:
                return error(
                    "Example: add sponsor Shree Caterers in-kind water cans"
                )
    
            # detect flat-based sponsor
            flat = (
                db.query(Flat)
                .filter(
                    Flat.flat_number == sponsor_name,
                    Flat.society_id == event.society_id
                )
                .first()
            )
    
            if flat:
                flat_id = flat.id
                sponsor_name = f"Flat {flat.flat_number}"
    
            ContributionService.add_contribution(
                db=db,
                event_id=event.id,
                society_id=event.society_id,
                contribution_type="in_kind",
                source_name=sponsor_name,
                flat_id=flat_id,
                in_kind_details=details,
                performed_by=member.id,
                notes="Via WhatsApp"
            )
    
            return success("🤝 In-kind sponsor added successfully.")
    
        # ------------------------------------------------
        # MONETARY SPONSOR
        # ------------------------------------------------
        parts = raw.split()
    
        if len(parts) < 2:
            return error("Example: add sponsor Shree Caterers 5000")
    
        try:
            amount = int(parts[-1])
        except ValueError:
            return error("Amount must be numeric. Example: add sponsor ABC 5000")
    
        sponsor_name = " ".join(parts[:-1]).strip()
    
        if not sponsor_name:
            return error("Sponsor name is required.")
    
        # detect flat-based sponsor
        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == sponsor_name,
                Flat.society_id == event.society_id
            )
            .first()
        )
    
        if flat:
            flat_id = flat.id
            sponsor_name = f"Flat {flat.flat_number}"
    
        ContributionService.add_contribution(
            db=db,
            event_id=event.id,
            society_id=event.society_id,
            contribution_type="sponsor",
            source_name=sponsor_name,
            flat_id=flat_id,
            amount=amount,
            performed_by=member.id,
            notes="Via WhatsApp"
        )
    
        return success("🤝 Sponsor added successfully.")

    
    if intent == "REFUND_SPONSOR":
        if not is_action_allowed(member.role, "REFUND"):
            return warning("Only Treasurer or Chairman can refund sponsors.")
    
        parts = message.split()
    
        if len(parts) < 6:
            return error(
                "Example: refund sponsor SP-001 500 reason banner cancelled"
            )
    
        contribution_code = parts[2]
        
        # ✅ amount is ALWAYS the token after contribution code
        try:
            amount = int(parts[3])
        except ValueError:
            return error("Invalid refund amount. Example: refund sponsor SP-007 500 reason xyz")
    
        # reason = everything after 'reason'
        if "reason" not in parts:
            return error("Please specify reason. Example: refund sponsor SP-007 500 reason xyz")
    
        reason_index = parts.index("reason")
        reason = " ".join(parts[reason_index + 1:]).strip()
    
        if not reason:
            return error("Refund reason is required.")
    
        try:
            ContributionRefundService.process_refund(
                db=db,
                event_id=event.id,
                contribution_code=contribution_code,
                amount=amount,
                reason=reason,
                performed_by=member.id
            )
        except Exception as exc:
            return error(str(exc))
    
        return success(f"↩️ Sponsor refund processed ({contribution_code}).")

    return None
