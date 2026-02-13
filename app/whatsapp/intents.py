#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:06:33 2026

@author: anonymous
"""

# app/whatsapp/intents.py

INTENTS = {
    # ========= MOST SPECIFIC (multi-word, high risk of conflict) =========

    # sponsor
    "REFUND_SPONSOR": "refund sponsor",
    "ADD_SPONSOR": "add sponsor",

    # approvals (specific before generic)
    "APPROVE_PAYMENT": "approve payment",
    "APPROVE_REFUND": "approve refund",
    "APPROVE": "approve user",

    # join
    "JOIN_STATUS": "join status",
    "JOIN": "join",

    # channel identity onboarding
    "LINK_MEMBER": "link member",
    "VERIFY_PHONE": "verify phone",

    # reports (specific phrases first)
    "BLOCK_REPORT": "block report",
    "PARTICIPATION_REPORT": "participation report",
    "PENDING_PAYMENTS": "pending payments",
    "PAYMENT_REQUESTS": "payment requests",
    "REFUND_REQUESTS": "refund requests",
    "EXPORT_REPORT": "report export",
    "SUMMARY": "summary",

    # actions
    "ADD_PASS": "add pass",
    "ADD_EXPENSE": "expense",
    "ADD_EVENT": "add event",
    "REMIND_FLAT": "remind",

    # payments & refunds (generic AFTER sponsor-specific)
    "REFUND": "refund",
    "PAY": "pay",

    # onboarding admin
    "PENDING_USERS": "pending users",

    # ========= PERSONAL (read-only, very specific) =========
    "MY_PASS": "my pass",
    "MY_PAYMENT_REQUESTS": "my payment requests",
    "MY_REFUND_REQUESTS": "my refund requests",
    "MY_PAYMENTS": "my payments",
    "MY_BALANCE": "my balance",
    "MY_STATUS": "my status",

    # ========= HELP (last, lowest risk) =========
    "HELP": "help",
    "COMMANDS": "commands",
}
