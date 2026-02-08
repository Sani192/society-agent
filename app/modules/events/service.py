#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:26:38 2026

@author: anonymous
"""

# app/modules/events/service.py

from sqlalchemy.orm import Session
from datetime import datetime

from app.workflows.engine import WorkflowEngine
from app.db.models import Event, WorkflowState, AuditLog


class EventService:

    @staticmethod
    def create_event(
        db: Session,
        *,
        society_id,
        name,
        event_date,
        food_types,
        created_by,
        charge_per_adult=None,
        charge_per_child=None,
        payment_deadline=None
    ):
        """
        Creates a new event and initializes workflow state.
        """

        # 1️ Create Event
        event = Event(
            society_id=society_id,
            name=name,
            event_date=event_date,
            food_types=food_types,
            charge_per_adult=charge_per_adult,
            charge_per_child=charge_per_child,
            payment_deadline=payment_deadline,
            status="DRAFT",
            created_by=created_by
        )

        db.add(event)
        db.flush()  # IMPORTANT: get event.id before commit

        # 2️ Initialize Workflow State
        workflow = WorkflowState(
            event_id=event.id,
            current_state="DRAFT",
            allowed_next_states=["ACTIVE"]
        )

        db.add(workflow)

        # 3️ Audit Log
        audit = AuditLog(
            society_id=society_id,
            entity_type="event",
            entity_id=event.id,
            action="CREATE_EVENT",
            reason="Initial event creation",
            performed_by=created_by
        )

        db.add(audit)

        # 4️ Commit transaction
        db.commit()

        return event
    
    @staticmethod
    def activate_event(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()
    
        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ACTIVATE_EVENT"
        )
    
        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="event",
                entity_id=event_id,
                action="ACTIVATE_EVENT",
                reason=override_reason,
                performed_by=performed_by
            )
    
        event.status = "ACTIVE"
        workflow.current_state = "ACTIVE"
        workflow.allowed_next_states = ["PAYMENT_LOCKED"]
    
        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="ACTIVATE_EVENT",
            reason=override_reason or "Normal transition",
            performed_by=performed_by
        ))
    
        db.commit()
        
    @staticmethod
    def lock_passes(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="LOCK_PASSES"
        )

        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="event",
                entity_id=event_id,
                action="LOCK_PASSES",
                reason=override_reason,
                performed_by=performed_by
            )

        event.status = "PAYMENT_LOCKED"
        workflow.current_state = "PAYMENT_LOCKED"
        workflow.allowed_next_states = ["EVENT_DAY"]

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="LOCK_PASSES",
            reason=override_reason or "Deadline reached",
            performed_by=performed_by
        ))

        db.commit()

    @staticmethod
    def start_event_day(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="START_EVENT"
        )

        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="event",
                entity_id=event_id,
                action="START_EVENT",
                reason=override_reason,
                performed_by=performed_by
            )

        event.status = "EVENT_DAY"
        workflow.current_state = "EVENT_DAY"
        workflow.allowed_next_states = ["CLOSE_EVENT"]

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="START_EVENT",
            reason=override_reason or "Event day started",
            performed_by=performed_by
        ))

        db.commit()
        
    @staticmethod
    def close_event(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="CLOSE_EVENT"
        )

        if not decision.allowed:
            if not override_reason:
                raise Exception(decision.message)
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="event",
                entity_id=event_id,
                action="CLOSE_EVENT",
                reason=override_reason,
                performed_by=performed_by
            )

        event.status = "CLOSED"
        workflow.current_state = "CLOSED"
        workflow.allowed_next_states = []

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="CLOSE_EVENT",
            reason=override_reason or "Event closed",
            performed_by=performed_by
        ))

        db.commit()

