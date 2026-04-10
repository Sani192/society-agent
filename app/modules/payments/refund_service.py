#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:44:25 2026

@author: anonymous
"""

# app/modules/payments/refund_service.py

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.db.models import (
    Event,
    Flat,
    Payment,
    Refund,
    AuditLog,
    WorkflowState,
)
from app.workflows.engine import WorkflowEngine
from app.workflows.rules import STATE_RULES
from app.modules.security.access_control import require_committee_action
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.validation import validate_uuid

logger = logging.getLogger(__name__)
_SERIALIZATION_RETRY_LIMIT = 3


def _is_serialization_error(exc: OperationalError) -> bool:
    original_error = getattr(exc, "orig", None)
    pg_code = getattr(original_error, "pgcode", None)
    if pg_code == "40001":
        return True
    return "could not serialize access" in str(exc).lower()


class RefundService:
    @staticmethod
    def _validate_identifiers(*, event_id, flat_id, performed_by, approved_request_id=None):
        event_id = validate_uuid(event_id, field_name="event_id")
        flat_id = validate_uuid(flat_id, field_name="flat_id")
        performed_by = validate_uuid(performed_by, field_name="member_id")
        if approved_request_id is not None:
            validate_uuid(approved_request_id, field_name="request_id")
        return event_id, flat_id, performed_by

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
        return "REQUEST_REFUND" in allowed_actions

    @staticmethod
    @log_service_call(logger, "RefundService.process_refund")
    def process_refund(
        db: Session,
        *,
        event_id,
        flat_id,
        amount,
        performed_by,
        reason,
        override_reason=None,
        require_approved_request_context=False,
        approved_request_id=None,
        approved_service_context=None,
    ):
        """
        Process a partial or full refund for a flat.
        """
        event_id, flat_id, performed_by = RefundService._validate_identifiers(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=performed_by,
            approved_request_id=approved_request_id,
        )

        context = build_log_context(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=performed_by
        )
        logger.info("Processing refund | amount=%s context=%s", amount, context)

        if amount <= 0:
            raise Exception("Refund amount must be greater than zero")

        if require_approved_request_context and RefundService._approval_request_required(
            db,
            event_id=event_id,
        ):
            if approved_request_id is None and not approved_service_context:
                raise Exception(
                    "Direct refund mutation is blocked: approval is required by policy."
                )


        for attempt in range(1, _SERIALIZATION_RETRY_LIMIT + 1):
            try:
                event = db.query(Event).filter(Event.id == event_id).first()
                flat = db.query(Flat).filter(Flat.id == flat_id).first()

                if not event or not flat:
                    raise Exception("Invalid event or flat")
                flat_society_id = getattr(flat, "society_id", event.society_id)
                if flat_society_id != event.society_id:
                    raise Exception("Flat does not belong to the event society")
                require_committee_action(
                    db,
                    society_id=event.society_id,
                    performed_by=performed_by,
                    action="REFUND",
                )
                logger.info("Validated event and flat | context=%s", context)

                decision = WorkflowEngine.check_action(
                    db=db,
                    event_id=event_id,
                    action="REQUEST_REFUND",
                    performed_by=performed_by,
                    override_reason=override_reason
                )

                if not decision.allowed:
                    logger.warning(
                        "Workflow denied refund action | requires_override=%s context=%s",
                        decision.requires_override,
                        context
                    )
                    if not decision.requires_override:
                        raise Exception(decision.message)
                    if not override_reason:
                        raise Exception(decision.message)
                    WorkflowEngine.apply_override(
                        db=db,
                        society_id=event.society_id,
                        event_id=event_id,
                        entity_type="refund",
                        entity_id=flat_id,
                        action="REQUEST_REFUND",
                        reason=override_reason,
                        performed_by=performed_by
                    )
                    logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

                payment = (
                    db.query(Payment)
                    .filter(
                        Payment.event_id == event_id,
                        Payment.flat_id == flat_id
                    )
                    .with_for_update()
                    .first()
                )

                if not payment or payment.paid_amount <= 0:
                    raise Exception("No payment available for refund")
                logger.info("Validated payment for refund | paid_amount=%s context=%s", payment.paid_amount, context)

                refunded_rows = (
                    db.query(Refund)
                    .filter(
                        Refund.event_id == event_id,
                        Refund.flat_id == flat_id,
                        Refund.status == "refunded"
                    )
                    .with_for_update()
                    .all()
                )
                total_refunded = sum(r.amount for r in refunded_rows)

                if amount + total_refunded > payment.paid_amount:
                    raise Exception("Refund amount exceeds paid amount")
                logger.info(
                    "Refund amounts validated after lock | total_refunded=%s context=%s",
                    total_refunded,
                    context
                )

                # Create refund record
                refund = Refund(
                    event_id=event_id,
                    flat_id=flat_id,
                    amount=amount,
                    reason=reason,
                    status="refunded",
                    created_by=performed_by
                )
                db.add(refund)
                db.flush()
                logger.info("Created refund record | amount=%s context=%s", amount, context)

                total_refunded_after_insert = (
                    db.query(func.coalesce(func.sum(Refund.amount), 0))
                    .filter(
                        Refund.event_id == event_id,
                        Refund.flat_id == flat_id,
                        Refund.status == "refunded",
                    )
                    .scalar()
                )
                if total_refunded_after_insert > payment.paid_amount:
                    raise Exception("Refund amount exceeds paid amount")
                logger.info(
                    "Post-insert refund guard validated | total_refunded=%s context=%s",
                    total_refunded_after_insert,
                    context,
                )

                payment.status = "refunded"
                logger.info("Updated payment status to refunded | context=%s", context)

                # Audit log (ONE entry only)
                db.add(AuditLog(
                    society_id=event.society_id,
                    entity_type="refund",
                    entity_id=flat_id,
                    action="PROCESS_REFUND",
                    reason=(
                        f"OVERRIDE: {override_reason} | {reason}"
                        if override_reason
                        else reason
                    ),
                    performed_by=performed_by
                ))
                logger.info("Captured refund audit log | context=%s", context)

                db.commit()
                logger.info(
                    "Committed refund transaction | context=%s attempt=%s",
                    context,
                    attempt,
                )

                return refund
            except OperationalError as exc:
                db.rollback()
                if _is_serialization_error(exc) and attempt < _SERIALIZATION_RETRY_LIMIT:
                    logger.warning(
                        "Serialization conflict while processing refund; retrying | attempt=%s context=%s",
                        attempt,
                        context,
                    )
                    continue
                raise
            except Exception:
                db.rollback()
                raise

        raise Exception("Failed to process refund due to repeated serialization conflicts")
