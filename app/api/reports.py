#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 21:18:20 2026

@author: anonymous
"""
# app/api/reports.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Event, CommitteeMember, UserFlatMapping
from app.modules.reports.event_summary.service import EventSummaryReport
from app.modules.reports.personal.my_payment_service import MyPaymentReport
from app.modules.reports.expenses.expense_summary_service import ExpenseSummaryReport
from app.modules.reports.sponsors.sponsor_report_service import SponsorReport
from app.modules.reports.block.block_contribution_service import BlockContributionReport
from app.modules.reports.onboarding.onboarding_pending_service import OnboardingPendingReport
from app.modules.reports.governance.override_report_service import OverrideReport
from app.modules.reports.governance.audit_summary_service import AuditSummaryReport
from app.permissions.guard import is_action_allowed
from app.utils.response import success, warning, error

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/event-summary")
def event_summary(db: Session = Depends(get_db)):
    # latest event by default
    event = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .first()
    )

    if not event:
        return success("No events found.")

    data = EventSummaryReport.generate(db=db, event_id=event.id)
    return success(data)


@router.get("/pending-payments")
def pending_payments(phone_number: str, db: Session = Depends(get_db)):
    # auth: committee only
    member = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.phone_number == phone_number,
            CommitteeMember.is_active.is_(True)
        )
        .first()
    )

    if not member or not is_action_allowed(member.role, "PENDING_PAYMENTS"):
        return warning("You are not allowed to perform this action.")

    event = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .first()
    )

    if not event:
        return success([])

    from app.modules.reports.pending_payments.service import PendingPaymentsReport

    data = PendingPaymentsReport.generate(db=db, event_id=event.id)
    return success(data)


@router.get("/my-payment")
def my_payment(phone_number: str, db: Session = Depends(get_db)):
    # latest event
    event = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .first()
    )

    if not event:
        return success({
            "expected": 0,
            "paid": 0,
            "refunded": 0,
            "pending": 0,
            "status": "not_applicable"
        })

    # ✅ AUTHORIZE ANY APPROVED USER
    mapping = (
        db.query(UserFlatMapping)
        .filter(
            UserFlatMapping.society_id == event.society_id,
            UserFlatMapping.user_identifier == phone_number,
            UserFlatMapping.is_active.is_(True)
        )
        .first()
    )

    if not mapping:
        return error("You are not registered with this society.")

    try:
        data = MyPaymentReport.generate(
            db=db,
            society_id=event.society_id,
            event_id=event.id,
            user_identifier=phone_number
        )
        return success(data)
    except Exception as e:
        return error(str(e))
    
    
@router.get("/expense-summary")
def expense_summary(db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .first()
    )

    if not event:
        return success({})

    data = ExpenseSummaryReport.generate(db=db, event_id=event.id)
    return success(data)


@router.get("/sponsor-report")
def sponsor_report(db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .first()
    )

    if not event:
        return success([])

    data = SponsorReport.generate(db=db, event_id=event.id)
    return success(data)


@router.get("/block-contribution")
def block_contribution(db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .order_by(Event.created_at.desc())
        .first()
    )

    if not event:
        return success({})

    data = BlockContributionReport.generate(db=db, event_id=event.id)
    return success(data)


@router.get("/onboarding-pending")
def onboarding_pending(phone_number: str, db: Session = Depends(get_db)):
    member = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.phone_number == phone_number,
            CommitteeMember.is_active.is_(True)
        )
        .first()
    )

    if not member or not is_action_allowed(member.role, "ONBOARDING_PENDING"):
        return warning("You are not allowed to perform this action.")

    data = OnboardingPendingReport.generate(
        db=db,
        society_id=member.society_id
    )
    return success(data)


@router.get("/override-report")
def override_report(phone_number: str, db: Session = Depends(get_db)):
    member = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.phone_number == phone_number,
            CommitteeMember.is_active.is_(True)
        )
        .first()
    )

    if not member or not is_action_allowed(member.role, "OVERRIDE_REPORT"):
        return warning("You are not allowed to perform this action.")

    data = OverrideReport.generate(
        db=db,
        society_id=member.society_id
    )
    return success(data)


@router.get("/audit-summary")
def audit_summary(phone_number: str, db: Session = Depends(get_db)):
    member = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.phone_number == phone_number,
            CommitteeMember.is_active.is_(True)
        )
        .first()
    )

    if not member or not is_action_allowed(member.role, "AUDIT_SUMMARY"):
        return warning("You are not allowed to perform this action.")

    data = AuditSummaryReport.generate(
        db=db,
        society_id=member.society_id
    )
    return success(data)