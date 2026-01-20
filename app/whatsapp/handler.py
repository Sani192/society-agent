#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:33 2026

@author: anonymous
"""

# app/whatsapp/handler.py

from app.db.session import SessionLocal
from app.db.models import CommitteeMember, Event, Flat, Payment

from app.modules.events.food_pass_service import FoodPassService
from app.modules.onboarding.join_code_service import JoinCodeService
from app.modules.onboarding.onboarding_service import OnboardingService
from app.modules.onboarding.admin_approval_service import AdminApprovalService
from app.modules.onboarding.onboarding_query_service import OnboardingQueryService
from app.modules.onboarding.admin_query_service import AdminOnboardingQueryService
from app.modules.payments.payment_service import PaymentService
from app.modules.payments.refund_service import RefundService
from app.modules.expenses.expense_service import ExpenseService
#from app.modules.reports.event_summary import EventSummaryReport
#from app.modules.reports.pending_payment_report import PendingPaymentReport
from app.modules.users.user_flat_service import UserFlatService
from app.modules.users.user_query_service import UserQueryService
from app.utils.response import success, error, warning
from app.utils.guards import ensure_admin
from app.utils.logger import logger
from app.permissions.guard import is_action_allowed
from app.whatsapp.router import detect_intent
from app.whatsapp.parser import (
    parse_amount,
    parse_pass_counts,
    parse_reason
)

def handle_message(phone_number: str, message: str):
    logger.info(f"Incoming message from {phone_number}: {message}")
    db = SessionLocal()

    member = (
        db.query(CommitteeMember)
        .filter(CommitteeMember.phone_number == phone_number)
        .first()
    )

    if not member or not member.is_active:
        return error("You are not authorized.")

# =============================================================================
#     try:
#         ensure_admin(phone_number)
#     except Exception as e:
#         logger.exception("Unhandled error in WhatsApp handler")
#         return error("Something went wrong. Please contact admin.")
# =============================================================================


    event = db.query(Event).order_by(Event.created_at.desc()).first()

    intent = detect_intent(message)
    if not intent:
        return "❓ Sorry, I didn’t understand this command."

    try:
        # ---------- ADD PASS ----------
        if intent == "ADD_PASS":
            if not is_action_allowed(member.role, "ADD_PASS"):
                return warning(
                    "This action normally requires Secretary approval. "
                    "Please ask Chairman to override."
                )
        
            mappings = UserFlatService.get_flats_for_user(db=db, society_id=event.society_id, user_identifier=phone_number)
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")
            flat = db.query(Flat).get(mappings[0].flat_id)
        
            counts = parse_pass_counts(message)
        
            if sum(counts.values()) == 0:
                return error("Specify counts. Example: add pass veg 2 jain 1")
        
            FoodPassService.add_or_update_pass(
                db=db,
                event_id=event.id,
                flat_id=flat.id,
                veg_count=counts["veg"],
                jain_count=counts["jain"],
                kids_count=counts["kids"],
                charge_per_person=300,
                performed_by=member.id,
                override_reason="Via WhatsApp"
            )
        
            return success(
                f"✅ Pass updated: veg {counts['veg']}, jain {counts['jain']}, kids {counts['kids']}"
            )

        # ---------- PAYMENT ----------
        if intent == "PAY":
            if not is_action_allowed(member.role, "PAY"):
                return warning(
                    "This action normally requires Treasurer approval. "
                    "Please ask Chairman to override."
                )
            
            mappings = UserFlatService.get_flats_for_user(db=db, society_id=event.society_id, user_identifier=phone_number)
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")
            flat = db.query(Flat).get(mappings[0].flat_id)
            
            amount = parse_amount(message)
            if not amount:
                return error("Please specify amount. Example: pay 500")
            
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

        # ---------- REFUND ----------
        if intent == "REFUND":
            if not is_action_allowed(member.role, "REFUND"):
                return warning(
                    "This action normally requires Treasurer approval. "
                    "Please ask Chairman to override."
                )
            
            mappings = UserFlatService.get_flats_for_user(db=db, society_id=event.society_id, user_identifier=phone_number)
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")
            flat = db.query(Flat).get(mappings[0].flat_id)
        
            amount = parse_amount(message)
            reason = parse_reason(message)
        
            if not amount or not reason:
                return error("Example: refund 200 reason guest absent")
        
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


        # ---------- EXPENSE ----------
        if intent == "ADD_EXPENSE":
            if not is_action_allowed(member.role, "ADD_EXPENSE"):
                return warning(
                    "This action normally requires Secretary approval. "
                    "Please ask Chairman to override."
                )
            
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

        # ---------- SUMMARY ----------
# =============================================================================
#         if intent == "SUMMARY":
#             if not is_action_allowed(member.role, "ALL"):
#                 return warning(
#                     "This action normally requires approval. "
#                     "Please ask Chairman to override."
#                 )
#             
#             summary = EventSummaryReport.generate(db=db, event_id=event.id)
#             return success(
#                 f"📊 *{summary['event']}*\n"
#                 f"Income: ₹{summary['income']['flats']}\n"
#                 f"Expenses: ₹{summary['expenses']}\n"
#                 f"Closing Balance: ₹{summary['closing_balance']}"
#             )
# =============================================================================
        
        # ---------- PENDING PAYMENTS ----------
# =============================================================================
#         if intent == "PENDING_PAYMENTS":
#             if not is_action_allowed(member.role, "PAY"):
#                 return warning(
#                     "This action normally requires Treasurer approval."
#                 )
#         
#             pending = PendingPaymentReport.get_pending_flats(
#                 db=db,
#                 event_id=event.id,
#                 society_id=event.society_id
#             )
#         
#             if not pending:
#                 return success("🎉 All flats have completed payments.")
#         
#             lines = ["⏳ *Pending Payments*"]
#             for p in pending:
#                 lines.append(
#                     f"{p['flat']} – Pending ₹{p['pending']}"
#                 )
#         
#             return success("\n".join(lines))
# =============================================================================
        
        # ---------- REMIND FLAT ----------
        if intent == "REMIND_FLAT":
            if not is_action_allowed(member.role, "PAY"):
                return warning(
                    "This action normally requires Treasurer approval."
                )
        
            parts = message.split()
            if len(parts) < 2:
                return error("Example: remind A-101")
        
            flat_number = parts[1]
        
            payment = (
                db.query(Payment)
                .join(Flat)
                .filter(
                    Flat.flat_number == flat_number,
                    Payment.event_id == event.id,
                    Flat.society_id == event.society_id
                )
                .first()
            )
        
            if not payment:
                return error("Flat or payment not found.")
        
            pending_amount = payment.expected_amount - payment.paid_amount
            if pending_amount <= 0:
                return success(f"{flat_number} has no pending payment.")
        
            return success(
                f"📢 *Payment Reminder*\n\n"
                f"Dear {flat_number},\n"
                f"Your pending amount for *{event.name}* is ₹{pending_amount}.\n"
                f"Please pay at your convenience.\n\n"
                f"Thank you."
            )

        # ---------- JOIN SOCIETY ----------
        if intent == "JOIN":
            parts = message.split()
            if len(parts) < 3:
                return error("Example: join ABC123 A-101")
        
            join_code = parts[1]
            flat_number = parts[2]
        
            society = JoinCodeService.get_society_by_join_code(db, join_code)
            if not society:
                return error("Invalid join code.")
        
            result = OnboardingService.start_onboarding(
                db=db,
                society=society,
                user_identifier=phone_number,
                flat_number=flat_number
            )
        
            if result == "APPROVED":
                return success("✅ You are successfully added to the society.")
        
            return success(
                "⏳ Your request is sent for approval.\n"
                f"Request ID: *{result}*\n"
                "You will be notified once approved."
            )


        # ---------- APPROVE USER ----------
        if intent == "APPROVE":
            if not is_action_allowed(member.role, "ALL"):
                return warning("Only Chairman can approve users.")
            
            parts = message.split()
            if len(parts) < 3:
                return error("Example: approve user REQ-003")
            
            request_code = parts[2]
            
            AdminApprovalService.approve_user(
                db=db,
                society_id=event.society_id,
                request_code=request_code
            )
            
            return success(f"✅ User approved ({request_code})")

        
        # ---------- JOIN STATUS ----------
        if intent == "JOIN_STATUS":
            society = db.query(Event).order_by(Event.created_at.desc()).first()
            society_id = society.society_id
        
            status = OnboardingQueryService.get_user_join_status(
                db=db,
                society_id=society_id,
                user_identifier=phone_number
            )
        
            if status == "APPROVED":
                return success("✅ Your membership is approved.")
        
            if status == "PENDING":
                return success("⏳ Your join request is pending approval.")
        
            return error("You have not requested to join any society.")


        # ---------- PENDING USERS ----------
        if intent == "PENDING_USERS":
            if not is_action_allowed(member.role, "ALL"):
                return warning("Only Chairman can view pending users.")

            society = db.query(Event).order_by(Event.created_at.desc()).first()
            society_id = society.society_id

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

        
        # ---------- MY PASS ----------
        if intent == "MY_PASS":
            mappings = UserFlatService.get_flats_for_user(
                db=db,
                society_id=event.society_id,
                user_identifier=phone_number
            )
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")
        
            flat = db.query(Flat).get(mappings[0].flat_id)
        
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
        
        # ---------- MY PAYMENT ----------
        if intent == "MY_PAYMENT":
            mappings = UserFlatService.get_flats_for_user(
                db=db,
                society_id=event.society_id,
                user_identifier=phone_number
            )
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")
        
            flat = db.query(Flat).get(mappings[0].flat_id)
        
            summary = UserQueryService.get_my_payment_summary(
                db=db,
                event_id=event.id,
                flat_id=flat.id
            )
        
            return success(
                f"💰 Payment Summary\n"
                f"Paid: ₹{summary['paid']}\n"
                f"Refunded: ₹{summary['refunded']}\n"
                f"Net Paid: ₹{summary['net_paid']}"
            )
        
        # ---------- MY BALANCE ----------
        if intent == "MY_BALANCE":
            mappings = UserFlatService.get_flats_for_user(
                db=db,
                society_id=event.society_id,
                user_identifier=phone_number
            )
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")
        
            flat = db.query(Flat).get(mappings[0].flat_id)
        
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

        # ---------- MY STATUS ----------
        if intent == "MY_STATUS":
            mappings = UserFlatService.get_flats_for_user(
                db=db,
                society_id=event.society_id,
                user_identifier=phone_number
            )
            if not mappings:
                return error("Your flat is not registered. Please contact admin.")

            flat = db.query(Flat).get(mappings[0].flat_id)

            status = UserQueryService.get_my_status(
                db=db,
                event_id=event.id,
                flat_id=flat.id
            )

            return success(f"📌 Event Status: {status}")
        
        # ---------- HELP ----------
        if intent == "HELP":
            return success(
                "🤖 *Society Assistant Help*\n\n"
                "You can manage event participation, payments and view details.\n\n"
                "Type *commands* to see everything you can do."
            )

        # ---------- COMMANDS ----------
        if intent == "COMMANDS":
            return success(
                "📋 *Available Commands*\n\n"
                "🎫 *Participation*\n"
                "- add pass veg 2 jain 1\n"
                "- my pass\n"
                "- my status\n\n"
                "💰 *Payments*\n"
                "- pay 500\n"
                "- my payment\n"
                "- my balance\n\n"
                "🧾 *Expenses* (Committee)\n"
                "- expense water tanker 1200\n\n"
                "↩️ *Refunds* (Committee)\n"
                "- refund 200 reason guest absent\n\n"
                "📊 *Reports*\n"
                "- summary\n\n"
                "ℹ️ *Help*\n"
                "- help\n"
                "- commands"
            )


    except Exception as e:
        return error(str(e))

    finally:
        db.close()
