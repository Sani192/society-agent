#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:21:40 2026

@author: anonymous
"""

# app/workflows/engine.py

from app.workflows.rules import STATE_RULES
from app.db.models import WorkflowState, AuditLog, CommitteeMember
from sqlalchemy.orm import Session
from datetime import datetime


class WorkflowDecision:
    def __init__(self, allowed: bool, requires_override: bool, message: str):
        self.allowed = allowed
        self.requires_override = requires_override
        self.message = message


class WorkflowEngine:

    @staticmethod
    def check_action(
        db: Session,
        event_id,
        action: str,
        performed_by=None,
        override_reason=None
    ) -> WorkflowDecision:

        state_row = (
            db.query(WorkflowState)
            .filter(WorkflowState.event_id == event_id)
            .first()
        )

        if not state_row:
            return WorkflowDecision(
                allowed=False,
                requires_override=False,
                message="Workflow state not initialized for event"
            )

        current_state = state_row.current_state
        allowed_actions = STATE_RULES.get(current_state, set())

        if action in allowed_actions:
            return WorkflowDecision(
                allowed=True,
                requires_override=False,
                message="Action allowed"
            )

        if current_state == "CLOSED":
            if not performed_by:
                return WorkflowDecision(
                    allowed=False,
                    requires_override=False,
                    message="Override denied: performer required for CLOSED state"
                )

            member = (
                db.query(CommitteeMember)
                .filter(CommitteeMember.id == performed_by)
                .first()
            )

            if (
                not member
                or not member.is_active
                or member.role not in {"chairman", "secretary", "treasurer"}
            ):
                return WorkflowDecision(
                    allowed=False,
                    requires_override=False,
                    message="Override denied: only chairman, secretary, or treasurer may override CLOSED state"
                )

            if not override_reason or not override_reason.strip():
                return WorkflowDecision(
                    allowed=False,
                    requires_override=False,
                    message="Override denied: reason required for CLOSED state"
                )

        # Action not normally allowed → override possible
        return WorkflowDecision(
            allowed=False,
            requires_override=True,
            message=f"Action '{action}' requires override in state '{current_state}'"
        )
    
    @staticmethod
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
        audit = AuditLog(
            society_id=society_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=f"OVERRIDE_{action}",
            reason=reason,
            performed_by=performed_by,
            performed_at=datetime.utcnow()
        )

        db.add(audit)
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
#             performed_at=datetime.utcnow()
#         )
# 
#         db.add(audit)
#         db.commit()
# =============================================================================
