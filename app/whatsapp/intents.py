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
    "LIST_COMMITTEE_MEMBERS": "committee members",
    "ADD_COMMITTEE_MEMBER": "add committee member",
    "REMOVE_COMMITTEE_MEMBER": "remove committee member",
    "CHANGE_COMMITTEE_ROLE": "change committee role",

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
    "REPORT_OPTIONS": "report options",
    "SUMMARY": "summary",

    # actions
    "ADD_PASS": "add pass",
    "ADD_EXPENSE": "expense",
    "ADD_EVENT": "add event",
    "ANNOUNCE_EVENT": "announce event",
    "ANNOUNCE_SOCIETY": "announce society",
    "CLOSE_EVENT": "close event",
    "ACTIVATE_EVENT": "activate event",
    "LOCK_PASSES": "lock passes",
    "START_EVENT": "start event",
    "GENERATE_FOOD_TOKENS": "generate food tokens",
    "OPEN_FOOD_COUNTER": "open food counter",
    "VERIFY_FOOD_TOKEN": "verify food token",
    "SCAN_FOOD_QR": "scan food qr",
    "SERVE_FOOD_FLAT": "serve flat",
    "FLAT_PASS_STATUS": "flat passes",
    "TOKEN_STATUS": "token status",
    "FOOD_DASHBOARD": "food dashboard",
    "REMIND_FLAT": "remind",

    # payments & refunds (generic AFTER sponsor-specific)
    "REFUND": "refund",
    "PAY": "pay",

    # onboarding admin
    "PENDING_USERS": "pending users",

    # ========= PERSONAL (read-only, very specific) =========
    "MY_PASS": "my pass",
    "MY_TOKENS": "my tokens",
    "MY_PAYMENT_REQUESTS": "my payment requests",
    "MY_REFUND_REQUESTS": "my refund requests",
    "MY_PAYMENTS": "my payments",
    "MY_BALANCE": "my balance",
    "MY_STATUS": "my status",

    "MENU": "menu",

    # ========= HELP (last, lowest risk) =========
    "HELP": "help",
}

TELEGRAM_ONLY_INTENTS = {
    "LINK_MEMBER": "link member",
    "VERIFY_PHONE": "verify phone",
}

WHATSAPP_INTENTS = {
    intent: keyword
    for intent, keyword in INTENTS.items()
    if intent not in TELEGRAM_ONLY_INTENTS
}
