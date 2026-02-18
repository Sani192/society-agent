#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:21:04 2026

@author: anonymous
"""

# app/workflows/rules.py

# Workflow action inventory and execution path
# action -> service.method + user-facing entrypoint intent/handler
WORKFLOW_ACTION_PATHS = {
    "CREATE_EVENT": "EventService.create_event <- ADD_EVENT via handle_committee_intent",
    "ACTIVATE_EVENT": "EventService.activate_event <- ACTIVATE_EVENT via handle_committee_intent",
    "LOCK_PASSES": "EventService.lock_passes <- LOCK_PASSES via handle_committee_intent",
    "START_EVENT": "EventService.start_event_day <- START_EVENT via handle_committee_intent",
    "CLOSE_EVENT": "EventService.close_event <- CLOSE_EVENT via handle_committee_intent",
    "ADD_PASS": "FoodPassService.add_or_update_pass <- ADD_PASS via handle_public_intent",
    "MARK_PAID": "PaymentService.record_payment <- PAY via handle_public_intent",
    "ADD_EXPENSE": "ExpenseService.add_expense <- ADD_EXPENSE via handle_committee_intent",
    "ADD_CONTRIBUTION": "ContributionService.add_contribution <- ADD_SPONSOR via handle_committee_intent",
    "REQUEST_PAYMENT": "PaymentRequestService.request_payment <- PAY via handle_public_intent",
    "REQUEST_REFUND": "RefundRequestService.request_refund <- REFUND via handle_public_intent",
    "REFUND_CONTRIBUTION": "ContributionRefundService.process_refund <- REFUND_SPONSOR via handle_committee_intent",
}

# What actions are allowed in each state
LOCKED_ACTIONS = {
    "MARK_PAID",
    "ADD_EXPENSE",
    "ADD_CONTRIBUTION",
    "REQUEST_PAYMENT",
    "REQUEST_REFUND",
    "REFUND_CONTRIBUTION",
    "START_EVENT"
}

STATE_RULES = {
    "DRAFT": {
        "CREATE_EVENT",
        "ACTIVATE_EVENT"
    },
    "ACTIVE": {
        "ADD_PASS",
        "MARK_PAID",
        "ADD_EXPENSE",
        "ADD_CONTRIBUTION",
        "REQUEST_PAYMENT",
        "REQUEST_REFUND",
        "REFUND_CONTRIBUTION",
        "LOCK_PASSES"
    },
    "LOCKED": LOCKED_ACTIONS,
    "EVENT_DAY": {
        "ADD_EXPENSE",
        "ADD_CONTRIBUTION",
        "REQUEST_PAYMENT",
        "REQUEST_REFUND",
        "REFUND_CONTRIBUTION",
        "CLOSE_EVENT"
    },
    "CLOSED": {
        # Normally read-only
    }
}
