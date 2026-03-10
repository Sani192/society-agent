#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reset the latest event state and transactional data."""

from app.db.models import Event, EventExpense, EventFoodPass, Payment, Refund, WorkflowState
from app.db.session import SessionLocal


def reset_latest_event(db) -> None:
    event = db.query(Event).order_by(Event.created_at.desc()).first()
    if event is None:
        raise ValueError("No event found")

    db.query(EventFoodPass).filter(EventFoodPass.event_id == event.id).delete()
    db.query(Payment).filter(Payment.event_id == event.id).delete()
    db.query(Refund).filter(Refund.event_id == event.id).delete()
    db.query(EventExpense).filter(EventExpense.event_id == event.id).delete()

    workflow = db.query(WorkflowState).filter(WorkflowState.event_id == event.id).first()
    if workflow is None:
        raise ValueError(f"No workflow state found for event {event.id}")

    workflow.current_state = "DRAFT"
    workflow.allowed_next_states = ["ACTIVE"]
    event.status = "DRAFT"

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        reset_latest_event(db)
        print("✅ Event reset to DRAFT (history preserved)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
