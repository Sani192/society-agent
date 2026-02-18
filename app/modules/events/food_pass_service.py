#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:52:44 2026

@author: anonymous
"""

# app/modules/events/food_pass_service.py

import logging
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import (
    Event,
    Flat,
    EventFoodPass,
    Payment,
    WorkflowState,
    AuditLog
)
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class FoodPassService:

    @staticmethod
    @log_service_call(logger, "FoodPassService.add_or_update_pass")
    def add_or_update_pass(
        db: Session,
        *,
        event_id,
        flat_id,
        veg_count=0,
        jain_count=0,
        kids_count=0,
        charge_per_adult,
        charge_per_child,
        performed_by,
        override_reason=None
    ):
        """
        Add or update food pass for a flat in an event.
        """
        context = build_log_context(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=performed_by
        )
        logger.info(
            "Adding/updating food pass | veg=%s jain=%s kids=%s context=%s",
            veg_count,
            jain_count,
            kids_count,
            context
        )

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")
        logger.info("Validated event and flat for food pass | context=%s", context)

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_PASS",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            logger.warning(
                "Workflow denied food pass action | requires_override=%s context=%s",
                decision.requires_override,
                context
            )
            if not decision.requires_override:
                raise Exception(decision.message)
            if not override_reason:
                raise Exception(decision.message)
            if not performed_by:
                raise Exception("Override denied: performer required")
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="food_pass",
                entity_id=flat_id,
                action="ADD_PASS",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        total_adults = veg_count + jain_count
        total_persons = total_adults + kids_count

        if total_persons <= 0:
            raise Exception("At least one food count must be greater than zero")

        total_amount = (total_adults * charge_per_adult) + (kids_count * charge_per_child)
        logger.info("Calculated pass amount | total_amount=%s context=%s", total_amount, context)

        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id
            )
            .first()
        )

        if food_pass:
            food_pass.veg_count = veg_count
            food_pass.jain_count = jain_count
            food_pass.kids_count = kids_count
            food_pass.total_amount = total_amount
            food_pass.is_participating = True
            food_pass.updated_at = datetime.utcnow()
            action = "UPDATE_PASS"
            logger.info("Updated existing food pass | context=%s", context)
        else:
            food_pass = EventFoodPass(
                event_id=event_id,
                flat_id=flat_id,
                veg_count=veg_count,
                jain_count=jain_count,
                kids_count=kids_count,
                total_amount=total_amount,
                is_participating=True,
                is_locked=False
            )
            db.add(food_pass)
            action = "ADD_PASS"
            logger.info("Created new food pass | context=%s", context)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="food_pass",
            entity_id=flat_id,
            action=action,
            reason=(
                f"OVERRIDE: {override_reason}"
                if override_reason
                else "Normal pass entry"
            ),
            performed_by=performed_by
        ))
        logger.info("Captured food pass audit log | action=%s context=%s", action, context)

        payment = (
            db.query(Payment)
            .filter(
                Payment.event_id == event_id,
                Payment.flat_id == flat_id
            )
            .first()
        )

        if not payment:
            payment = Payment(
                event_id=event_id,
                flat_id=flat_id,
                expected_amount=total_amount,
                paid_amount=0,
                status="pending"
            )
            logger.info("Initialized payment tracking for pass | context=%s", context)
        else:
            payment.expected_amount = total_amount
            if payment.paid_amount >= total_amount:
                payment.status = "paid"
            else:
                payment.status = "partial" if payment.paid_amount > 0 else "pending"
            logger.info(
                "Updated payment expectations | expected_amount=%s status=%s context=%s",
                total_amount,
                payment.status,
                context
            )

        db.add(payment)

        db.commit()
        logger.info("Committed food pass transaction | context=%s", context)

        return food_pass

    @staticmethod
    @log_service_call(logger, "FoodPassService.mark_not_participating")
    def mark_not_participating(
        db: Session,
        *,
        event_id,
        flat_id,
        performed_by,
        override_reason=None
    ):
        """
        Mark a flat as not participating in the event.
        """
        context = build_log_context(
            event_id=event_id,
            flat_id=flat_id,
            performed_by=performed_by
        )
        logger.info("Marking flat not participating | context=%s", context)

        event = db.query(Event).filter(Event.id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_PASS",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            logger.warning(
                "Workflow denied mark not participating | requires_override=%s context=%s",
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
                entity_type="food_pass",
                entity_id=flat_id,
                action="REMOVE_PASS",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        food_pass = (
            db.query(EventFoodPass)
            .filter(
                EventFoodPass.event_id == event_id,
                EventFoodPass.flat_id == flat_id
            )
            .first()
        )

        if food_pass:
            food_pass.veg_count = 0
            food_pass.jain_count = 0
            food_pass.kids_count = 0
            food_pass.total_amount = 0
            food_pass.is_participating = False
            food_pass.updated_at = datetime.utcnow()
            logger.info("Updated existing food pass to not participating | context=%s", context)
        else:
            food_pass = EventFoodPass(
                event_id=event_id,
                flat_id=flat_id,
                veg_count=0,
                jain_count=0,
                kids_count=0,
                total_amount=0,
                is_participating=False,
                is_locked=False
            )
            db.add(food_pass)
            logger.info("Created non-participating food pass | context=%s", context)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="food_pass",
            entity_id=flat_id,
            action="MARK_NOT_PARTICIPATING",
            reason=(
                f"OVERRIDE: {override_reason}"
                if override_reason
                else "Flat opted out"
            ),
            performed_by=performed_by
        ))
        logger.info("Captured non-participation audit log | context=%s", context)

        db.commit()
        logger.info("Committed food pass opt-out transaction | context=%s", context)

        return food_pass
