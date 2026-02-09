#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:26:38 2026

@author: anonymous
"""

# app/modules/events/service.py

import logging
from sqlalchemy.orm import Session
from datetime import datetime

from app.workflows.engine import WorkflowEngine
from app.db.models import Event, WorkflowState, AuditLog
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class EventService:

    @staticmethod
    @log_service_call(logger, "EventService.create_event")
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
        context = build_log_context(society_id=society_id, performed_by=created_by)
        logger.info(
            "Creating event | name=%s date=%s context=%s",
            name,
            event_date,
            context
        )

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
        logger.info("Created event record | event_id=%s context=%s", event.id, context)

        # 2️ Initialize Workflow State
        workflow = WorkflowState(
            event_id=event.id,
            current_state="DRAFT",
            allowed_next_states=["ACTIVE"]
        )

        db.add(workflow)
        logger.info("Initialized workflow state | event_id=%s context=%s", event.id, context)

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
        logger.info("Captured event audit log | event_id=%s context=%s", event.id, context)

        # 4️ Commit transaction
        db.commit()
        logger.info("Committed event creation | event_id=%s context=%s", event.id, context)

        return event
    
    @staticmethod
    @log_service_call(logger, "EventService.activate_event")
    def activate_event(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info("Activating event | context=%s", context)
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()
    
        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ACTIVATE_EVENT",
            performed_by=performed_by,
            override_reason=override_reason
        )
    
        if not decision.allowed:
            logger.warning(
                "Workflow denied activation | requires_override=%s context=%s",
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
                entity_type="event",
                entity_id=event_id,
                action="ACTIVATE_EVENT",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)
    
        event.status = "ACTIVE"
        workflow.current_state = "ACTIVE"
        workflow.allowed_next_states = ["LOCKED"]
        logger.info("Updated event workflow state to ACTIVE | context=%s", context)
    
        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="ACTIVATE_EVENT",
            reason=override_reason or "Normal transition",
            performed_by=performed_by
        ))
        logger.info("Captured activation audit log | context=%s", context)
    
        db.commit()
        logger.info("Committed event activation | context=%s", context)
        
    @staticmethod
    @log_service_call(logger, "EventService.lock_passes")
    def lock_passes(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info("Locking passes | context=%s", context)
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="LOCK_PASSES",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            logger.warning(
                "Workflow denied lock passes | requires_override=%s context=%s",
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
                entity_type="event",
                entity_id=event_id,
                action="LOCK_PASSES",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        event.status = "LOCKED"
        workflow.current_state = "LOCKED"
        workflow.allowed_next_states = ["EVENT_DAY"]
        logger.info("Updated event workflow state to LOCKED | context=%s", context)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="LOCK_PASSES",
            reason=override_reason or "Deadline reached",
            performed_by=performed_by
        ))
        logger.info("Captured lock passes audit log | context=%s", context)

        db.commit()
        logger.info("Committed lock passes transition | context=%s", context)

    @staticmethod
    @log_service_call(logger, "EventService.start_event_day")
    def start_event_day(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info("Starting event day | context=%s", context)
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="START_EVENT",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            logger.warning(
                "Workflow denied start event | requires_override=%s context=%s",
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
                entity_type="event",
                entity_id=event_id,
                action="START_EVENT",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        event.status = "EVENT_DAY"
        workflow.current_state = "EVENT_DAY"
        workflow.allowed_next_states = ["CLOSE_EVENT"]
        logger.info("Updated event workflow state to EVENT_DAY | context=%s", context)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="START_EVENT",
            reason=override_reason or "Event day started",
            performed_by=performed_by
        ))
        logger.info("Captured start event audit log | context=%s", context)

        db.commit()
        logger.info("Committed start event transition | context=%s", context)
        
    @staticmethod
    @log_service_call(logger, "EventService.close_event")
    def close_event(
        db: Session,
        *,
        event_id,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info("Closing event | context=%s", context)
        event = db.query(Event).filter(Event.id == event_id).first()
        workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event_id).first()

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="CLOSE_EVENT",
            performed_by=performed_by,
            override_reason=override_reason
        )

        if not decision.allowed:
            logger.warning(
                "Workflow denied close event | requires_override=%s context=%s",
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
                entity_type="event",
                entity_id=event_id,
                action="CLOSE_EVENT",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        event.status = "CLOSED"
        workflow.current_state = "CLOSED"
        workflow.allowed_next_states = []
        logger.info("Updated event workflow state to CLOSED | context=%s", context)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="event",
            entity_id=event_id,
            action="CLOSE_EVENT",
            reason=override_reason or "Event closed",
            performed_by=performed_by
        ))
        logger.info("Captured close event audit log | context=%s", context)

        db.commit()
        logger.info("Committed close event transition | context=%s", context)
