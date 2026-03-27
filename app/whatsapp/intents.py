#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:06:33 2026

@author: anonymous
"""

# app/whatsapp/intents.py

SUPPORTED_INTENT_LANGUAGES = ("en", "hi", "gu")

INTENT_KEYWORDS_BY_LANGUAGE = {
    # ========= MOST SPECIFIC (multi-word, high risk of conflict) =========
    # sponsor
    "REFUND_SPONSOR": {"en": ["refund sponsor"], "hi": [], "gu": []},
    "ADD_SPONSOR": {"en": ["add sponsor"], "hi": [], "gu": []},
    "LIST_COMMITTEE_MEMBERS": {"en": ["committee members"], "hi": [], "gu": []},
    "ADD_COMMITTEE_MEMBER": {"en": ["add committee member"], "hi": [], "gu": []},
    "REMOVE_COMMITTEE_MEMBER": {"en": ["remove committee member"], "hi": [], "gu": []},
    "CHANGE_COMMITTEE_ROLE": {"en": ["change committee role"], "hi": [], "gu": []},
    # approvals (specific before generic)
    "APPROVE_PAYMENT": {"en": ["approve payment"], "hi": [], "gu": []},
    "APPROVE_REFUND": {"en": ["approve refund"], "hi": [], "gu": []},
    "APPROVE": {"en": ["approve user"], "hi": [], "gu": []},
    # join
    "JOIN_STATUS": {"en": ["join status"], "hi": [], "gu": []},
    "JOIN": {"en": ["join"], "hi": [], "gu": []},
    # channel identity onboarding
    "LINK_MEMBER": {"en": ["link member"], "hi": [], "gu": []},
    "VERIFY_PHONE": {"en": ["verify phone"], "hi": [], "gu": []},
    # reports (specific phrases first)
    "BLOCK_REPORT": {"en": ["block report"], "hi": [], "gu": []},
    "PARTICIPATION_REPORT": {"en": ["participation report"], "hi": [], "gu": []},
    "PENDING_PAYMENTS": {"en": ["pending payments"], "hi": [], "gu": []},
    "PAYMENT_REQUESTS": {"en": ["payment requests"], "hi": [], "gu": []},
    "REFUND_REQUESTS": {"en": ["refund requests"], "hi": [], "gu": []},
    "REPORT_OPTIONS": {"en": ["report options"], "hi": ["रिपोर्ट विकल्प"], "gu": ["રિપોર્ટ વિકલ્પો"]},
    "SUMMARY": {"en": ["summary"], "hi": ["सारांश"], "gu": ["સારાંશ"]},
    # actions
    "ADD_PASS": {"en": ["add pass"], "hi": [], "gu": []},
    "ADD_EXPENSE": {"en": ["expense"], "hi": [], "gu": []},
    "ADD_EVENT": {"en": ["add event"], "hi": [], "gu": []},
    "ANNOUNCE_EVENT": {"en": ["announce event"], "hi": [], "gu": []},
    "ANNOUNCE_SOCIETY": {"en": ["announce society"], "hi": [], "gu": []},
    "CLOSE_EVENT": {"en": ["close event"], "hi": [], "gu": []},
    "ACTIVATE_EVENT": {"en": ["activate event"], "hi": [], "gu": []},
    "LOCK_PASSES": {"en": ["lock passes"], "hi": [], "gu": []},
    "START_EVENT": {"en": ["start event"], "hi": [], "gu": []},
    "GENERATE_FOOD_TOKENS": {"en": ["generate food tokens"], "hi": [], "gu": []},
    "OPEN_FOOD_COUNTER": {"en": ["open food counter"], "hi": [], "gu": []},
    "VERIFY_FOOD_TOKEN": {"en": ["verify food token"], "hi": [], "gu": []},
    "SCAN_FOOD_QR": {"en": ["scan food qr"], "hi": [], "gu": []},
    "SERVE_FOOD_FLAT": {"en": ["serve flat"], "hi": [], "gu": []},
    "FLAT_PASS_STATUS": {"en": ["flat passes"], "hi": [], "gu": []},
    "TOKEN_STATUS": {"en": ["token status"], "hi": [], "gu": []},
    "FOOD_DASHBOARD": {"en": ["food dashboard"], "hi": [], "gu": []},
    "REMIND_FLAT": {"en": ["remind"], "hi": [], "gu": []},
    # payments & refunds (generic AFTER sponsor-specific)
    "REFUND": {"en": ["refund"], "hi": ["रिफंड", "वापसी"], "gu": ["રિફંડ", "પરત"]},
    "PAY": {"en": ["pay"], "hi": ["पे", "भुगतान"], "gu": ["ચુકવો", "ચુકવણી"]},
    # onboarding admin
    "PENDING_USERS": {"en": ["pending users"], "hi": [], "gu": []},
    # ========= PERSONAL (read-only, very specific) =========
    "MY_PASS": {"en": ["my pass"], "hi": [], "gu": []},
    "MY_TOKENS": {"en": ["my tokens"], "hi": [], "gu": []},
    "MY_PAYMENT_REQUESTS": {"en": ["my payment requests"], "hi": [], "gu": []},
    "MY_REFUND_REQUESTS": {"en": ["my refund requests"], "hi": [], "gu": []},
    "MY_PAYMENTS": {"en": ["my payments"], "hi": [], "gu": []},
    "MY_BALANCE": {"en": ["my balance"], "hi": [], "gu": []},
    "MY_STATUS": {"en": ["my status"], "hi": [], "gu": []},
    "MENU": {"en": ["menu"], "hi": ["मेनू"], "gu": ["મેનુ"]},
    # ========= HELP (last, lowest risk) =========
    "HELP": {"en": ["help"], "hi": ["मदद"], "gu": ["મદદ"]},
}

TELEGRAM_ONLY_INTENTS = {"LINK_MEMBER", "VERIFY_PHONE"}


def _primary_keyword(intent_keywords: dict[str, list[str]], *, lang: str = "en") -> str:
    by_lang = intent_keywords.get(lang) or []
    if by_lang:
        return by_lang[0]
    fallback = intent_keywords.get("en") or []
    return fallback[0] if fallback else ""


INTENTS = {
    intent: _primary_keyword(keyword_sets, lang="en")
    for intent, keyword_sets in INTENT_KEYWORDS_BY_LANGUAGE.items()
}

WHATSAPP_INTENTS = {
    intent: keyword
    for intent, keyword in INTENTS.items()
    if intent not in TELEGRAM_ONLY_INTENTS
}

WHATSAPP_INTENT_KEYWORDS_BY_LANGUAGE = {
    intent: keywords
    for intent, keywords in INTENT_KEYWORDS_BY_LANGUAGE.items()
    if intent not in TELEGRAM_ONLY_INTENTS
}
