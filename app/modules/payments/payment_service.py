#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 15:19:25 2026

@author: anonymous
"""

# app/modules/payments/payment_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import (
    Event,
    Flat,
    Payment,
    EventFoodPass,
    AuditLog,
    WorkflowState,
)
from app.workflows.engine import WorkflowEngine
from app.workflows.rules import STATE_RULES
from app.modules.security.access_control import require_committee_action
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class PaymentService:

    @staticmethod
    def _approval_request_required(db: Session, *, event_id) -> bool:
        workflow_state = (
            db.query(WorkflowState)
            .filter(WorkflowState.event_id == event_id)
            .first()
        )
        if not workflow_state:
            return False

        allowed_actions = STATE_RULES.get(workflow_state.current_state, set())
        return "REQUEST_PAYMENT" in allowed_actions

    @staticmethod
    @log_service_call(logger, "PaymentService.record_payment")
    def record_payment(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        payment_mode,
        performed_by,
        override_reason=None,
        require_approved_request_context=False,
        approved_request_id=None,
        approved_service_context=None,
    ):
        """
        Record a payment (partial or full) for a flat in an event.
        """
        context = build_log_context(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=performed_by
        )
        logger.info("Recording payment | amount=%s mode=%s context=%s", amount, payment_mode, context)

        if amount <= 0:
            raise Exception("Payment amount must be greater than zero")

        if require_approved_request_context and PaymentService._approval_request_required(
            db,
            event_id=event_id,
        ):
            if approved_request_id is None and not approved_service_context:
                raise Exception(
                    "Direct payment mutation is blocked: approval is required by policy."
                )


        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")
        if flat.society_id != event.society_id:
            raise Exception("Flat does not belong to the event society")
        require_committee_action(
            db,
            society_id=event.society_id,
            performed_by=performed_by,
            action="PAY",
        )
        logger.info("Validated event and flat | context=%s", context)

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="MARK_PAID",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            logger.warning(
                "Workflow denied payment action | requires_override=%s context=%s",
                decision.requires_override,
                context
            )
            if not decision.requires_override:
                raise Exception(decision.message)
            if not override_reason:
                raise Exception(decision.message)
            # Override permission only – no audit here
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="payment",
                entity_id=flat_id,
                action="MARK_PAID",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id,
                EventFoodPass.is_participating
            )
            .first()
        )

        if not food_pass:
            raise Exception("Food pass not found or flat not participating")
        logger.info("Resolved food pass | expected_amount=%s context=%s", food_pass.total_amount, context)

        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .first()
        )

        expected_amount = food_pass.total_amount

        if not payment:
            payment = Payment(
                event_id=event_id,
                flat_id=flat_id,
                expected_amount=expected_amount,
                paid_amount=0,
                status="pending"
            )
            db.add(payment)
            logger.info("Initialized payment record | expected_amount=%s context=%s", expected_amount, context)

        payment.paid_amount += amount
        payment.payment_mode = payment_mode
        payment.paid_at = utc_now()

        if payment.paid_amount >= expected_amount:
            payment.status = "paid"
        else:
            payment.status = "partial"
        logger.info(
            "Updated payment totals | paid_amount=%s status=%s context=%s",
            payment.paid_amount,
            payment.status,
            context
        )

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="payment",
            entity_id=flat_id,
            action="MARK_PAID",
            reason=(
                f"OVERRIDE: {override_reason}"
                if override_reason
                else f"Payment received via {payment_mode}"
            ),
            performed_by=performed_by
        ))
        logger.info("Captured payment audit log | context=%s", context)

        db.commit()
        logger.info("Committed payment transaction | context=%s", context)

        return payment
