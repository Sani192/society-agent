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
    "REFUND_SPONSOR": {"en": ["refund sponsor"], "hi": ["प्रायोजक रिफंड"], "gu": ["પ્રાયોજક રિફંડ"]},
    "ADD_SPONSOR": {"en": ["add sponsor"], "hi": ["प्रायोजक जोड़ें"], "gu": ["પ્રાયોજક ઉમેરો"]},
    "LIST_COMMITTEE_MEMBERS": {"en": ["committee members"], "hi": ["समिति सदस्य"], "gu": ["સમિતિ સભ્યો"]},
    "ADD_COMMITTEE_MEMBER": {"en": ["add committee member"], "hi": ["समिति सदस्य जोड़ें"], "gu": ["સમિતિ સભ્ય ઉમેરો"]},
    "REMOVE_COMMITTEE_MEMBER": {"en": ["remove committee member"], "hi": ["समिति सदस्य हटाएं"], "gu": ["સમિતિ સભ્ય દૂર કરો"]},
    "CHANGE_COMMITTEE_ROLE": {"en": ["change committee role"], "hi": ["समिति भूमिका बदलें"], "gu": ["સમિતિ ભૂમિકા બદલો"]},
    # approvals (specific before generic)
    "APPROVE_PAYMENT": {"en": ["approve payment"], "hi": ["भुगतान स्वीकृत करें"], "gu": ["ચુકવણી મંજૂર કરો"]},
    "APPROVE_REFUND": {"en": ["approve refund"], "hi": ["रिफंड स्वीकृत करें"], "gu": ["રિફંડ મંજૂર કરો"]},
    "APPROVE": {"en": ["approve user"], "hi": ["उपयोगकर्ता स्वीकृत करें"], "gu": ["વપરાશકર્તા મંજૂર કરો"]},
    # join
    "JOIN_STATUS": {"en": ["join status"], "hi": ["जॉइन स्थिति"], "gu": ["જોડાવાની સ્થિતિ"]},
    "JOIN": {"en": ["join"], "hi": ["जॉइन"], "gu": ["જોડાઓ"]},
    # channel identity onboarding
    "LINK_MEMBER": {"en": ["link member"], "hi": ["सदस्य लिंक करें"], "gu": ["સભ્ય લિંક કરો"]},
    "VERIFY_PHONE": {"en": ["verify phone"], "hi": ["फोन सत्यापित करें"], "gu": ["ફોન ચકાસો"]},
    # reports (specific phrases first)
    "BLOCK_REPORT": {"en": ["block report"], "hi": ["ब्लॉक रिपोर्ट"], "gu": ["બ્લોક રિપોર્ટ"]},
    "PARTICIPATION_REPORT": {"en": ["participation report"], "hi": ["भागीदारी रिपोर्ट"], "gu": ["ભાગીદારી રિપોર્ટ"]},
    "PENDING_PAYMENTS": {"en": ["pending payments"], "hi": ["लंबित भुगतान"], "gu": ["બાકી ચુકવણીઓ"]},
    "PAYMENT_REQUESTS": {"en": ["payment requests"], "hi": ["भुगतान अनुरोध"], "gu": ["ચુકવણી વિનંતીઓ"]},
    "REFUND_REQUESTS": {"en": ["refund requests"], "hi": ["रिफंड अनुरोध"], "gu": ["રિફંડ વિનંતીઓ"]},
    "REPORT_OPTIONS": {"en": ["report options"], "hi": ["रिपोर्ट विकल्प"], "gu": ["રિપોર્ટ વિકલ્પો"]},
    "SUMMARY": {"en": ["summary"], "hi": ["सारांश"], "gu": ["સારાંશ"]},
    # actions
    "ADD_PASS": {"en": ["add pass"], "hi": ["पास जोड़ें"], "gu": ["પાસ ઉમેરો"]},
    "ADD_EXPENSE": {"en": ["expense"], "hi": ["खर्च", "खर्च जोड़ें"], "gu": ["ખર્ચ", "ખર્ચ ઉમેરો"]},
    "ADD_EVENT": {"en": ["add event"], "hi": ["इवेंट जोड़ें"], "gu": ["ઇવેન્ટ ઉમેરો"]},
    "ANNOUNCE_EVENT": {"en": ["announce event"], "hi": ["इवेंट घोषणा"], "gu": ["ઇવેન્ટ જાહેરાત"]},
    "ANNOUNCE_SOCIETY": {"en": ["announce society"], "hi": ["सोसायटी घोषणा"], "gu": ["સોસાયટી જાહેરાત"]},
    "CLOSE_EVENT": {"en": ["close event"], "hi": ["इवेंट बंद करें"], "gu": ["ઇવેન્ટ બંધ કરો"]},
    "ACTIVATE_EVENT": {"en": ["activate event"], "hi": ["इवेंट सक्रिय करें"], "gu": ["ઇવેન્ટ સક્રિય કરો"]},
    "LOCK_PASSES": {"en": ["lock passes"], "hi": ["पास लॉक करें"], "gu": ["પાસ લોક કરો"]},
    "START_EVENT": {"en": ["start event"], "hi": ["इवेंट शुरू करें"], "gu": ["ઇવેન્ટ શરૂ કરો"]},
    "GENERATE_FOOD_TOKENS": {"en": ["generate food tokens"], "hi": ["फूड टोकन बनाएं"], "gu": ["ફૂડ ટોકન બનાવો"]},
    "OPEN_FOOD_COUNTER": {"en": ["open food counter"], "hi": ["फूड काउंटर खोलें"], "gu": ["ફૂડ કાઉન્ટર ખોલો"]},
    "VERIFY_FOOD_TOKEN": {"en": ["verify food token"], "hi": ["फूड टोकन सत्यापित करें"], "gu": ["ફૂડ ટોકન ચકાસો"]},
    "SCAN_FOOD_QR": {"en": ["scan food qr"], "hi": ["फूड क्यूआर स्कैन करें"], "gu": ["ફૂડ ક્યુઆર સ્કેન કરો"]},
    "SERVE_FOOD_FLAT": {"en": ["serve flat"], "hi": ["फ्लैट सर्व करें"], "gu": ["ફ્લેટ સર્વ કરો"]},
    "FLAT_PASS_STATUS": {"en": ["flat passes"], "hi": ["फ्लैट पास"], "gu": ["ફ્લેટ પાસ"]},
    "TOKEN_STATUS": {"en": ["token status"], "hi": ["टोकन स्थिति"], "gu": ["ટોકન સ્થિતિ"]},
    "FOOD_DASHBOARD": {"en": ["food dashboard"], "hi": ["फूड डैशबोर्ड"], "gu": ["ફૂડ ડેશબોર્ડ"]},
    "REMIND_FLAT": {"en": ["remind"], "hi": ["याद दिलाएं"], "gu": ["યાદ અપાવો"]},
    # payments & refunds (generic AFTER sponsor-specific)
    "REFUND": {"en": ["refund"], "hi": ["रिफंड", "वापसी"], "gu": ["રિફંડ", "પરત"]},
    "PAY": {"en": ["pay"], "hi": ["पे", "भुगतान"], "gu": ["ચુકવો", "ચુકવણી"]},
    # onboarding admin
    "PENDING_USERS": {"en": ["pending users"], "hi": ["लंबित उपयोगकर्ता"], "gu": ["બાકી વપરાશકર્તાઓ"]},
    # ========= PERSONAL (read-only, very specific) =========
    "MY_PASS": {"en": ["my pass"], "hi": ["मेरा पास"], "gu": ["મારો પાસ"]},
    "MY_TOKENS": {"en": ["my tokens"], "hi": ["मेरे टोकन"], "gu": ["મારા ટોકન"]},
    "MY_PAYMENT_REQUESTS": {"en": ["my payment requests"], "hi": ["मेरे भुगतान अनुरोध"], "gu": ["મારી ચુકવણી વિનંતીઓ"]},
    "MY_REFUND_REQUESTS": {"en": ["my refund requests"], "hi": ["मेरे रिफंड अनुरोध"], "gu": ["મારી રિફંડ વિનંતીઓ"]},
    "MY_PAYMENTS": {"en": ["my payments"], "hi": ["मेरे भुगतान"], "gu": ["મારી ચુકવણીઓ"]},
    "MY_BALANCE": {"en": ["my balance"], "hi": ["मेरा बैलेंस"], "gu": ["મારું બેલેન્સ"]},
    "MY_STATUS": {"en": ["my status"], "hi": ["मेरी स्थिति"], "gu": ["મારી સ્થિતિ"]},
    "MENU": {"en": ["menu"], "hi": ["मेनू", "मुख्य मेनू"], "gu": ["મેનુ", "મુખ્ય મેનુ"]},
    "MORE": {"en": ["more"], "hi": ["और", "अधिक"], "gu": ["વધુ"]},
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
