#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:49:24 2026

@author: anonymous
"""

# app/modules/expenses/expense_service.py

from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import Event, EventExpense, AuditLog
from app.workflows.engine import WorkflowEngine


class ExpenseService:

    @staticmethod
    def add_expense(
        db: Session,
        *,
        event_id,
        description,
        amount,
        performed_by,
        override_reason=None
    ):
        if amount <= 0:
            raise Exception("Expense amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_EXPENSE"
        )

        is_override = False

        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
            is_override = True
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="expense",
                entity_id=event_id,
                action="ADD_EXPENSE",
                reason=override_reason,
                performed_by=performed_by
            )

        expense = EventExpense(
            event_id=event_id,
            description=description,
            amount=amount,
            is_override=is_override,
            override_reason=override_reason if is_override else None
        )

        db.add(expense)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="expense",
            entity_id=event_id,
            action="ADD_EXPENSE",
            reason=(
                f"OVERRIDE: {override_reason}"
                if is_override
                else description
            ),
            performed_by=performed_by
        ))

        db.commit()
        return expense
