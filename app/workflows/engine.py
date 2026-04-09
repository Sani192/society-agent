#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:21:40 2026

@author: anonymous
"""

# app/workflows/engine.py

import logging
from app.workflows.rules import STATE_RULES
from app.db.models import WorkflowState, AuditLog, CommitteeMember
from sqlalchemy.orm import Session
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.time import utc_now

logger = logging.getLogger(__name__)
OVERRIDE_ROLES = {"chairman", "secretary", "treasurer"}


class WorkflowDecision:
    def __init__(self, allowed: bool, requires_override: bool, message: str):
        self.allowed = allowed
        self.requires_override = requires_override
        self.message = message


class WorkflowEngine:

    @staticmethod
    @log_service_call(logger, "WorkflowEngine.check_action")
    def check_action(
        db: Session,
        event_id,
        action: str,
        performed_by=None,
        override_reason=None
    ) -> WorkflowDecision:
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info(
            "Checking workflow action",
            extra={"action": action, "result": "started", "context": context},
        )
        state_row = (
            db.query(WorkflowState)
            .filter(WorkflowState.event_id == event_id)
            .first()
        )

        if not state_row:
            logger.warning(
                "Workflow state missing",
                extra={"action": action, "result": "state_missing", "context": context},
            )
            return WorkflowDecision(
                allowed=False,
                requires_override=False,
                message="Workflow state not initialized for event"
            )

        current_state = state_row.current_state
        allowed_actions = STATE_RULES.get(current_state, set())
        logger.info(
            "Resolved workflow state",
            extra={
                "action": action,
                "result": "state_resolved",
                "workflow_state": current_state,
                "context": context,
            },
        )

        if action in allowed_actions:
            logger.info(
                "Workflow action allowed",
                extra={"action": action, "result": "allowed", "context": context},
            )
            return WorkflowDecision(
                allowed=True,
                requires_override=False,
                message="Action allowed"
            )

        state_suffix = " for CLOSED state" if current_state == "CLOSED" else ""

        if not performed_by or (isinstance(performed_by, str) and not performed_by.strip()):
            logger.warning(
                "Override denied: missing performer",
                extra={"action": action, "result": "override_denied_missing_performer", "context": context},
            )
            return WorkflowDecision(
                allowed=False,
                requires_override=False,
                message=f"Override denied: performer required{state_suffix}"
            )

        member = (
            db.query(CommitteeMember)
            .filter(CommitteeMember.id == performed_by)
            .first()
        )

        if (
            not member
            or not member.is_active
            or member.role not in OVERRIDE_ROLES
        ):
            logger.warning(
                "Override denied: invalid member",
                extra={"action": action, "result": "override_denied_invalid_member", "context": context},
            )
            return WorkflowDecision(
                allowed=False,
                requires_override=False,
                message=f"Override denied: only chairman, secretary, or treasurer may override{state_suffix}"
            )

        if not override_reason or not override_reason.strip():
            logger.warning(
                "Override denied: reason required",
                extra={"action": action, "result": "override_denied_reason_required", "context": context},
            )
            return WorkflowDecision(
                allowed=False,
                requires_override=False,
                message=f"Override denied: reason required{state_suffix}"
            )

        # Action not normally allowed → override possible
        logger.info(
            "Workflow requires override",
            extra={"action": action, "result": "requires_override", "context": context},
        )
        return WorkflowDecision(
            allowed=False,
            requires_override=True,
            message=f"Action '{action}' requires override in state '{current_state}'"
        )
    
    @staticmethod
    @log_service_call(logger, "WorkflowEngine.apply_override")
    def apply_override(
        db: Session,
        *,
        society_id,
        event_id,
        entity_type,
        entity_id,
        action,
        reason,
        performed_by
    ):
        context = build_log_context(event_id=event_id, society_id=society_id, performed_by=performed_by)
        logger.info(
            "Applying workflow override",
            extra={
                "action": action,
                "result": "override_apply_started",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "context": context,
            },
        )
        audit = AuditLog(
            society_id=society_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=f"OVERRIDE_{action}",
            reason=reason,
            performed_by=performed_by,
            performed_at=utc_now()
        )

        db.add(audit)
        logger.info(
            "Captured override audit log",
            extra={"action": action, "result": "override_audit_logged", "context": context},
        )
        return audit


# =============================================================================
#     @staticmethod
#     def apply_override(
#         db: Session,
#         *,
#         society_id,
#         event_id,
#         entity_type,
#         entity_id,
#         action,
#         reason,
#         performed_by
#     ):
#         audit = AuditLog(
#             society_id=society_id,
#             entity_type=entity_type,
#             entity_id=entity_id,
#             action=f"OVERRIDE_{action}",
#             reason=reason,
#             performed_by=performed_by,
#             performed_at=utc_now()
#         )
# 
#         db.add(audit)
#         db.commit()
# =============================================================================
