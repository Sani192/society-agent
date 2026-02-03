#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:52:44 2026

@author: anonymous
"""

# app/modules/events/food_pass_service.py

from sqlalchemy.orm import Session
from datetime import datetime

from app.db.models import (
    Event,
    Flat,
    Payment,
    EventFoodPass,
    WorkflowState,
    AuditLog
)
from app.workflows.engine import WorkflowEngine


class FoodPassService:

    @staticmethod
    def add_or_update_pass(
        db: Session,
        *,
        event_id,
        flat_id,
        veg_count=0,
        jain_count=0,
        kids_count=0,
        charge_per_person,
        performed_by,
        override_reason=None
    ):
        """
        Add or update food pass for a flat in an event.
        """

        event = db.query(Event).filter(Event.id == event_id).first()
        flat = db.query(Flat).filter(Flat.id == flat_id).first()

        if not event or not flat:
            raise Exception("Invalid event or flat")

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_PASS"
        )

        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
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

        total_persons = veg_count + jain_count + kids_count

        if total_persons <= 0:
            raise Exception("At least one food count must be greater than zero")

        total_amount = total_persons * charge_per_person

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
            db.add(payment)
        else:
            payment.expected_amount = total_amount
            payment.status = (
                "paid"
                if payment.paid_amount >= total_amount
                else "pending"
            )

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


        db.commit()

        return food_pass

    @staticmethod
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

        event = db.query(Event).filter(Event.id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_PASS"
        )

        if not decision.allowed:
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

        db.commit()

        return food_pass
