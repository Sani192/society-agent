#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 14:21:04 2026

@author: anonymous
"""

# app/workflows/rules.py

# What actions are allowed in each state
LOCKED_ACTIONS = {
    "MARK_PAID",
    "ADD_VENDOR",
    "ADD_EXPENSE",
    "ADD_CONTRIBUTION",
    "REQUEST_REFUND",
    "ANNOUNCE",
    "START_EVENT"
}

STATE_RULES = {
    "DRAFT": {
        "CREATE_EVENT",
        "EDIT_EVENT",
        "ACTIVATE_EVENT"
    },
    "ACTIVE": {
        "ADD_PASS",
        "MARK_PAID",
        "ADD_VENDOR",
        "ADD_EXPENSE",
        "ADD_CONTRIBUTION",
        "REQUEST_REFUND",
        "ANNOUNCE",
        "LOCK_PASSES"
    },
    "LOCKED": LOCKED_ACTIONS,
    "PAYMENT_LOCKED": LOCKED_ACTIONS,
    "EVENT_DAY": {
        "MARK_COLLECTED",
        "ADD_EXPENSE",
        "ADD_CONTRIBUTION",
        "CLOSE_EVENT"
    },
    "CLOSED": {
        # Normally read-only
    }
}
