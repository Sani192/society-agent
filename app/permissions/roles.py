#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:56:07 2026

@author: anonymous
"""

# app/permissions/roles.py

ROLE_ACTIONS = {
    "chairman": {
        "ALL"
    },
    "secretary": {
        "ADD_PASS",
        "ADD_EXPENSE",
        "SUMMARY",
        "PENDING_PAYMENTS",
        "ONBOARDING_PENDING",
        "OVERRIDE_REPORT",
        "AUDIT_SUMMARY"
    },
    "treasurer": {
        "PAY",
        "REFUND",
        "SUMMARY",
        "PENDING_PAYMENTS"
    }
}
