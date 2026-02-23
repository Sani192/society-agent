#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:49:24 2026

@author: anonymous
"""

# app/modules/expenses/expense_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import Event, EventExpense, AuditLog
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class ExpenseService:

    @staticmethod
    @log_service_call(logger, "ExpenseService.add_expense")
    def add_expense(
        db: Session,
        *,
        event_id,
        description,
        amount,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info(
            "Adding expense | amount=%s description=%s context=%s",
            amount,
            description,
            context
        )
        if amount <= 0:
            raise Exception("Expense amount must be greater than zero")

        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")
        logger.info("Validated event for expense | context=%s", context)

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_EXPENSE",
            performed_by=performed_by,
            override_reason=override_reason
        )

        is_override = False

        if not decision.allowed:
            logger.warning(
                "Workflow denied expense action | requires_override=%s context=%s",
                decision.requires_override,
                context
            )
            if not decision.requires_override:
                raise Exception(decision.message)
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
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        expense = EventExpense(
            event_id=event_id,
            description=description,
            amount=amount,
            is_override=is_override,
            override_reason=override_reason if is_override else None
        )

        db.add(expense)
        logger.info("Created expense record | context=%s", context)

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
        logger.info("Captured expense audit log | context=%s", context)

        db.commit()
        logger.info("Committed expense transaction | context=%s", context)
        return expense
