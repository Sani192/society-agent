#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhatsApp UI routing and command handling."""

from datetime import timedelta

from app.db.session import SessionLocal
from app.db.models import CommitteeMember, Event, EventFoodToken, Flat, MemberIdentity, UserFlatMapping
from app.modules.users.member_identity_service import MemberIdentityService
from app.modules.users.language_service import normalize_language_code, resolve_sender_language, set_preferred_language
from app.channels.whatsapp.intents import WHATSAPP_INTENTS
from app.modules.users.user_query_service import UserQueryService
from app.handlers.shared.common import (
    get_latest_event,
    get_latest_event_for_society,
    resolve_flat,
    resolve_sender_society_id,
)
from app.channels.whatsapp.response_templates import format_currency
from app.channels.whatsapp.ui import (
    add_or_update_pass_prompt,
    build_committee_approvals_sections,
    build_committee_food_collection_sections,
    build_committee_operations_more_sections,
    build_committee_operations_sections,
    build_committee_reports_sections,
    build_committee_sections,
    build_committee_management_sections,
    build_finance_sections,
    build_main_dashboard_sections,
    build_make_payment_sections,
    build_my_account_sections,
    build_participation_sections,
    build_payments_sections,
    build_reports_sections,
    build_society_sections,
    format_financial_overview,
    payment_custom_amount_prompt,
    refund_request_prompt,
)
from app.utils.guards import ensure_committee_member, ensure_member_of_society, normalize_phone
from app.permissions.command_policy import get_event_state, is_member_action_visible
from app.utils.logger import logger
from app.utils.time import utc_now
from app.modules.events.food_collection_service import FoodCollectionService
from app.channels.whatsapp.finance_action_session import (
    FinanceActionSessionState,
    build_finance_action_session_key,
    clear_finance_action_session,
    get_finance_action_session,
    save_finance_action_session,
)
from app.channels.whatsapp.join_session import (
    JoinSessionState,
    build_join_session_key,
    save_join_session,
)
from app.channels.whatsapp.committee_management_session import (
    CommitteeManagementSessionState,
    build_committee_management_session_key,
    clear_committee_management_session,
    get_committee_management_session,
    save_committee_management_session,
)
from app.channels.whatsapp.approval_flow import _send_approval_selection_list

WHATSAPP_LIST_MAX_ROWS = 10
WHATSAPP_MORE_REPORTS_ROW_ID = "export::more-reports"
WHATSAPP_APPROVAL_ROW_LIMIT = 10
WHATSAPP_REPORT_EVENT_ROW_PREFIX = "report-event::"
WHATSAPP_FINANCE_EVENT_ROW_PREFIX = "finance-event::"
COMMITTEE_ROLE_ROW_PREFIX = "committee-role::"
COMMITTEE_ADD_MEMBER_ROW_PREFIX = "committee-add-member::"
COMMITTEE_MEMBER_ROW_PREFIX = "committee-member::"
COMMITTEE_CONFIRM_ROW_PREFIX = "committee-confirm::"
FOOD_VERIFY_TOKEN_ROW_PREFIX = "food-verify-token::"
FOOD_SCAN_QR_ROW_PREFIX = "food-scan-qr::"
FOOD_TOKEN_STATUS_ROW_PREFIX = "food-token-status::"
FOOD_SERVE_FLAT_ROW_PREFIX = "food-serve-flat::"
FOOD_FLAT_STATUS_ROW_PREFIX = "food-flat-status::"
LANGUAGE_ROW_PREFIX = "language::"
COMMITTEE_ROLE_OPTIONS = [
    ("chairman", "Chairman"),
    ("treasurer", "Treasurer"),
    ("secretary", "Secretary"),
    ("committee_member", "Committee Member"),
]

FINANCE_EVENT_ACTIONS = {"VIEW_BALANCE", "MAKE_PAYMENT"}

REPORT_INTENTS_REQUIRING_EVENT = {"SUMMARY", "BLOCK_REPORT", "PARTICIPATION_REPORT"}
REPORT_AUTO_EVENT_STATES = {"ACTIVE", "LOCKED", "EVENT_DAY"}


UI_TEXT = {
    "en": {
        "finance.select_event_header": "Select Event",
        "finance.select_event_body": "This action needs an event. Choose one to continue.",
        "finance.select_event_button": "Choose Event",
        "dashboard.header": "Society Control Panel",
        "dashboard.select_action": "Select an action",
        "dashboard.open_all_sections": "All available sections",
        "common.open": "Open",
        "common.select": "Select",
        "common.confirm": "Confirm",
        "common.back": "Back",
        "common.back_description": "Go to previous menu",
        "common.main_menu": "Main Menu",
        "common.main_menu_description": "Go to main menu",
        "common.navigation": "Navigation",
        "language.choose_body": "Choose your preferred language",
        "language.select_button": "Select",
        "language.section_title": "Languages",
        "language.updated": "✅ Your language has been updated to English.",
        "language.unsupported": "Unsupported language selection. Please choose from the list.",
        "registration.header": "Registration Required",
        "registration.body": "You are not registered yet. Tap below to join your society.",
        "registration.join": "Join Society",
        "participation.header": "Participation",
        "participation.body": "Participation",
        "payments.header": "Your Financial Overview",
        "payments.body": "Select an action",
        "my_account.body": "Account actions",
        "society.body": "Society actions",
        "finance.body": "Finance actions",
        "administration.header": "Administration",
        "administration.select_area": "Select an area",
        "administration.approvals": "Approval actions",
        "administration.operations": "Operational actions",
        "administration.operations_more": "More operational actions",
        "administration.reports": "Report actions",
        "administration.food": "Food collection actions",
        "administration.committee": "Committee administration",
        "committee.header": "Committee",
        "committee.members": "Members",
        "committee.no_members": "No members available",
        "committee.add_header": "Add Committee Member",
        "committee.choose_member": "Choose a member",
        "committee.society_members": "Society Members",
        "committee.select_member_to_add": "Select member to add",
        "committee.select_role": "Select Role",
        "committee.assign_role": "Assign role: {role}",
        "committee.confirm_header": "Confirm",
        "committee.confirm_body": "Confirm {action} {member}{role_suffix}?",
        "committee.confirm_section": "Confirmation",
        "committee.confirm_yes": "Confirm",
        "committee.confirm_yes_description": "Proceed",
        "committee.confirm_no": "Cancel",
        "committee.confirm_no_description": "Discard",
        "committee.choose_role": "Choose role",
        "committee.change_role_header": "Change Committee Role",
        "committee.choose_new_role": "Choose new role",
        "committee.choose_member_remove": "Choose member to remove",
        "committee.choose_member_update": "Choose member to update",
        "make_payment.header": "Make Payment",
        "make_payment.outstanding_body": "Outstanding Amount: {amount}",
        "my_account.header": "My Account",
        "society.header": "Society",
        "finance.header": "Finance",
        "reports.header": "Reports",
        "reports.select_action": "Select a report action",
        "join.enter_code": "Please enter join code",
        "access.restricted": "Access restricted.",
        "event.none_contact_committee": "No active event found. Please contact committee.",
        "food.no_pending_tokens": "No pending tokens available.",
        "food.no_tokens": "No tokens available.",
        "food.pending_tokens": "Pending Tokens",
        "food.tokens": "Tokens",
        "food.no_flats_pending": "No flats with pending tokens found.",
        "food.flats": "Flats",
        "food.select_to_continue": "Select to continue",
        "food.verify_header": "Verify Food Token",
        "food.verify_body": "Select token to serve",
        "food.scan_header": "Scan Food QR",
        "food.scan_body": "Select scanned token",
        "food.status_header": "Token Status",
        "food.status_body": "Select token to inspect",
        "food.serve_flat_header": "Serve Flat",
        "food.serve_flat_body": "Select flat for fallback serve",
        "food.flat_passes_header": "Flat Passes",
        "food.flat_passes_body": "Select flat to view status",
        "food.served_token": "✅ Served token {token_code} ({food_type}).",
        "food.token_status_line": "🔎 Token {token_code} | {food_type} | {status}",
        "food.flat_not_found": "Flat not found.",
        "food.served_flat": "✅ Served {flat_number} using token {token_code}.",
        "food.flat_status_line": "📊 {flat_number} | Total {total_passes} | Served {served} | Remaining {remaining}",
        "food.status_served": "Served",
        "food.status_pending": "Pending",
        "common.error_with_reason": "❌ {error}",
        "participation.pass_updates_active_only": "Pass updates are available only when event is active.",
        "finance.no_outstanding": "No outstanding balance to pay.",
        "finance.payment_refund_active_only": "Payment and refund requests are available only when event is active.",
        "committee.no_society_context": "No society context found.",
        "committee.no_eligible_members_add": "No eligible members found to add.",
        "committee.view_none": "No committee members found.",
        "committee.view_header": "Committee members:",
        "committee.member_not_found": "Member not found.",
        "committee.invalid_role_selection": "Invalid role selection.",
        "committee.action_cancelled": "Action cancelled.",
        "committee.unable_add": "Unable to add member.",
        "committee.member_exists": "Member already exists in committee.",
        "committee.member_added": "Member added successfully",
        "committee.cannot_remove_last_chairman": "Cannot remove last chairman",
        "committee.member_removed": "Member removed successfully",
        "committee.unable_change_role": "Unable to change role.",
        "committee.role_updated": "Member role updated successfully",
        "committee.unable_process_action": "Unable to process committee action.",
        "committee.action.remove": "remove",
        "committee.action.assign_role_to": "assign role to",
        "committee.action.change_role_for": "change role for",
    },
    "hi": {
        "finance.select_event_header": "इवेंट चुनें",
        "finance.select_event_body": "इस कार्रवाई के लिए इवेंट चाहिए। आगे बढ़ने के लिए एक चुनें।",
        "finance.select_event_button": "इवेंट चुनें",
        "dashboard.header": "सोसाइटी कंट्रोल पैनल",
        "dashboard.select_action": "एक कार्रवाई चुनें",
        "dashboard.open_all_sections": "सभी उपलब्ध सेक्शन",
        "common.open": "खोलें",
        "common.select": "चुनें",
        "common.confirm": "पुष्टि करें",
        "common.back": "वापस",
        "common.back_description": "पिछले मेनू पर जाएँ",
        "common.main_menu": "मुख्य मेनू",
        "common.main_menu_description": "मुख्य मेनू पर जाएँ",
        "common.navigation": "नेविगेशन",
        "language.choose_body": "अपनी पसंदीदा भाषा चुनें",
        "language.select_button": "चुनें",
        "language.section_title": "भाषाएँ",
        "language.updated": "✅ आपकी भाषा हिन्दी में अपडेट कर दी गई है।",
        "language.unsupported": "भाषा चयन समर्थित नहीं है। कृपया सूची में से चुनें।",
        "registration.header": "पंजीकरण आवश्यक",
        "registration.body": "आप अभी पंजीकृत नहीं हैं। अपनी सोसाइटी से जुड़ने के लिए नीचे टैप करें।",
        "registration.join": "सोसाइटी जुड़ें",
        "participation.header": "भागीदारी",
        "participation.body": "भागीदारी",
        "payments.header": "आपका वित्तीय अवलोकन",
        "payments.body": "एक कार्रवाई चुनें",
        "my_account.body": "अकाउंट कार्रवाइयाँ",
        "society.body": "सोसाइटी कार्रवाइयाँ",
        "finance.body": "वित्तीय कार्रवाइयाँ",
        "administration.header": "प्रशासन",
        "administration.select_area": "एक क्षेत्र चुनें",
        "administration.approvals": "स्वीकृति कार्रवाइयाँ",
        "administration.operations": "संचालन कार्रवाइयाँ",
        "administration.operations_more": "और संचालन कार्रवाइयाँ",
        "administration.reports": "रिपोर्ट कार्रवाइयाँ",
        "administration.food": "भोजन वितरण कार्रवाइयाँ",
        "administration.committee": "समिति प्रशासन",
        "committee.header": "समिति",
        "committee.members": "सदस्य",
        "committee.no_members": "कोई सदस्य उपलब्ध नहीं है",
        "committee.add_header": "समिति सदस्य जोड़ें",
        "committee.choose_member": "एक सदस्य चुनें",
        "committee.society_members": "सोसाइटी सदस्य",
        "committee.select_member_to_add": "जोड़ने के लिए सदस्य चुनें",
        "committee.select_role": "भूमिका चुनें",
        "committee.assign_role": "भूमिका दें: {role}",
        "committee.confirm_header": "पुष्टि करें",
        "committee.confirm_body": "क्या आप {action} {member}{role_suffix} की पुष्टि करते हैं?",
        "committee.confirm_section": "पुष्टि",
        "committee.confirm_yes": "पुष्टि करें",
        "committee.confirm_yes_description": "आगे बढ़ें",
        "committee.confirm_no": "रद्द करें",
        "committee.confirm_no_description": "छोड़ें",
        "committee.choose_role": "भूमिका चुनें",
        "committee.change_role_header": "समिति भूमिका बदलें",
        "committee.choose_new_role": "नई भूमिका चुनें",
        "committee.choose_member_remove": "हटाने के लिए सदस्य चुनें",
        "committee.choose_member_update": "अपडेट करने के लिए सदस्य चुनें",
        "make_payment.header": "भुगतान करें",
        "make_payment.outstanding_body": "बकाया राशि: {amount}",
        "my_account.header": "मेरा अकाउंट",
        "society.header": "सोसाइटी",
        "finance.header": "वित्त",
        "reports.header": "रिपोर्ट",
        "reports.select_action": "रिपोर्ट कार्रवाई चुनें",
        "join.enter_code": "कृपया जॉइन कोड दर्ज करें",
        "access.restricted": "पहुँच प्रतिबंधित है।",
        "event.none_contact_committee": "कोई सक्रिय इवेंट नहीं मिला। कृपया समिति से संपर्क करें।",
        "food.no_pending_tokens": "कोई लंबित टोकन उपलब्ध नहीं है।",
        "food.no_tokens": "कोई टोकन उपलब्ध नहीं है।",
        "food.pending_tokens": "लंबित टोकन",
        "food.tokens": "टोकन",
        "food.no_flats_pending": "लंबित टोकन वाले फ्लैट नहीं मिले।",
        "food.flats": "फ्लैट",
        "food.select_to_continue": "आगे बढ़ने के लिए चुनें",
        "food.verify_header": "फूड टोकन सत्यापित करें",
        "food.verify_body": "सर्व करने के लिए टोकन चुनें",
        "food.scan_header": "फूड QR स्कैन करें",
        "food.scan_body": "स्कैन किया गया टोकन चुनें",
        "food.status_header": "टोकन स्थिति",
        "food.status_body": "जांच के लिए टोकन चुनें",
        "food.serve_flat_header": "फ्लैट सर्व करें",
        "food.serve_flat_body": "फॉलबैक सर्व के लिए फ्लैट चुनें",
        "food.flat_passes_header": "फ्लैट पास",
        "food.flat_passes_body": "स्थिति देखने के लिए फ्लैट चुनें",
        "food.served_token": "✅ टोकन {token_code} ({food_type}) सर्व किया गया।",
        "food.token_status_line": "🔎 टोकन {token_code} | {food_type} | {status}",
        "food.flat_not_found": "फ्लैट नहीं मिला।",
        "food.served_flat": "✅ टोकन {token_code} से {flat_number} सर्व किया गया।",
        "food.flat_status_line": "📊 {flat_number} | कुल {total_passes} | सर्व {served} | शेष {remaining}",
        "food.status_served": "सर्व",
        "food.status_pending": "लंबित",
        "common.error_with_reason": "❌ {error}",
        "participation.pass_updates_active_only": "पास अपडेट केवल तब उपलब्ध हैं जब इवेंट सक्रिय हो।",
        "finance.no_outstanding": "भुगतान करने के लिए कोई बकाया राशि नहीं है।",
        "finance.payment_refund_active_only": "पेमेंट और रिफंड अनुरोध केवल सक्रिय इवेंट में उपलब्ध हैं।",
        "committee.no_society_context": "कोई सोसाइटी संदर्भ नहीं मिला।",
        "committee.no_eligible_members_add": "जोड़ने के लिए कोई योग्य सदस्य नहीं मिला।",
        "committee.view_none": "कोई समिति सदस्य नहीं मिला।",
        "committee.view_header": "समिति सदस्य:",
        "committee.member_not_found": "सदस्य नहीं मिला।",
        "committee.invalid_role_selection": "अमान्य भूमिका चयन।",
        "committee.action_cancelled": "कार्रवाई रद्द की गई।",
        "committee.unable_add": "सदस्य जोड़ना संभव नहीं हुआ।",
        "committee.member_exists": "सदस्य पहले से समिति में है।",
        "committee.member_added": "सदस्य सफलतापूर्वक जोड़ दिया गया",
        "committee.cannot_remove_last_chairman": "अंतिम चेयरमैन को हटाया नहीं जा सकता",
        "committee.member_removed": "सदस्य सफलतापूर्वक हटाया गया",
        "committee.unable_change_role": "भूमिका बदलना संभव नहीं हुआ।",
        "committee.role_updated": "सदस्य की भूमिका सफलतापूर्वक अपडेट हुई",
        "committee.unable_process_action": "समिति कार्रवाई संसाधित नहीं की जा सकी।",
        "committee.action.remove": "हटाना",
        "committee.action.assign_role_to": "को भूमिका देना",
        "committee.action.change_role_for": "की भूमिका बदलना",
    },
    "gu": {
        "finance.select_event_header": "ઇવેન્ટ પસંદ કરો",
        "finance.select_event_body": "આ ક્રિયા માટે ઇવેન્ટ જરૂરી છે. આગળ વધવા માટે એક પસંદ કરો.",
        "finance.select_event_button": "ઇવેન્ટ પસંદ કરો",
        "dashboard.header": "સોસાયટી કન્ટ્રોલ પેનલ",
        "dashboard.select_action": "એક ક્રિયા પસંદ કરો",
        "dashboard.open_all_sections": "બધા ઉપલબ્ધ વિભાગો",
        "common.open": "ખોલો",
        "common.select": "પસંદ કરો",
        "common.confirm": "ખાતરી કરો",
        "common.back": "પાછળ",
        "common.back_description": "પાછલા મેનૂ પર જાઓ",
        "common.main_menu": "મુખ્ય મેનૂ",
        "common.main_menu_description": "મુખ્ય મેનૂ પર જાઓ",
        "common.navigation": "નેવિગેશન",
        "language.choose_body": "તમારી પસંદગીની ભાષા પસંદ કરો",
        "language.select_button": "પસંદ કરો",
        "language.section_title": "ભાષાઓ",
        "language.updated": "✅ તમારી ભાષા ગુજરાતી પર અપડેટ થઈ ગઈ છે.",
        "language.unsupported": "અસમર્થિત ભાષા પસંદગી. કૃપા કરીને યાદીમાંથી પસંદ કરો.",
        "registration.header": "નોંધણી જરૂરી",
        "registration.body": "તમે હજી નોંધાયેલા નથી. તમારી સોસાયટીમાં જોડાવા માટે નીચે ટૅપ કરો.",
        "registration.join": "સોસાયટી જોડાઓ",
        "participation.header": "ભાગીદારી",
        "participation.body": "ભાગીદારી",
        "payments.header": "તમારો નાણાકીય અવલોકન",
        "payments.body": "એક ક્રિયા પસંદ કરો",
        "my_account.body": "એકાઉન્ટ ક્રિયાઓ",
        "society.body": "સોસાયટી ક્રિયાઓ",
        "finance.body": "નાણાકીય ક્રિયાઓ",
        "administration.header": "પ્રશાસન",
        "administration.select_area": "એક વિસ્તાર પસંદ કરો",
        "administration.approvals": "મંજૂરી ક્રિયાઓ",
        "administration.operations": "ઓપરેશન ક્રિયાઓ",
        "administration.operations_more": "વધુ ઓપરેશન ક્રિયાઓ",
        "administration.reports": "રિપોર્ટ ક્રિયાઓ",
        "administration.food": "ફૂડ કલેક્શન ક્રિયાઓ",
        "administration.committee": "સમિતિ વહીવટ",
        "committee.header": "સમિતિ",
        "committee.members": "સભ્યો",
        "committee.no_members": "કોઈ સભ્ય ઉપલબ્ધ નથી",
        "committee.add_header": "સમિતિ સભ્ય ઉમેરો",
        "committee.choose_member": "એક સભ્ય પસંદ કરો",
        "committee.society_members": "સોસાયટી સભ્યો",
        "committee.select_member_to_add": "ઉમેરવા માટે સભ્ય પસંદ કરો",
        "committee.select_role": "ભૂમિકા પસંદ કરો",
        "committee.assign_role": "ભૂમિકા આપો: {role}",
        "committee.confirm_header": "ખાતરી કરો",
        "committee.confirm_body": "શું તમે {action} {member}{role_suffix} ની ખાતરી કરો છો?",
        "committee.confirm_section": "ખાતરી",
        "committee.confirm_yes": "ખાતરી કરો",
        "committee.confirm_yes_description": "આગળ વધો",
        "committee.confirm_no": "રદ કરો",
        "committee.confirm_no_description": "રદ કરો",
        "committee.choose_role": "ભૂમિકા પસંદ કરો",
        "committee.change_role_header": "સમિતિ ભૂમિકા બદલો",
        "committee.choose_new_role": "નવી ભૂમિકા પસંદ કરો",
        "committee.choose_member_remove": "દૂર કરવા માટે સભ્ય પસંદ કરો",
        "committee.choose_member_update": "અપડેટ કરવા માટે સભ્ય પસંદ કરો",
        "make_payment.header": "ચુકવણી કરો",
        "make_payment.outstanding_body": "બાકી રકમ: {amount}",
        "my_account.header": "મારું એકાઉન્ટ",
        "society.header": "સોસાયટી",
        "finance.header": "નાણા",
        "reports.header": "રિપોર્ટ્સ",
        "reports.select_action": "રિપોર્ટ માટે ક્રિયા પસંદ કરો",
        "join.enter_code": "કૃપા કરીને જોડાવાનો કોડ દાખલ કરો",
        "access.restricted": "પ્રવેશ પ્રતિબંધિત છે.",
        "event.none_contact_committee": "કોઈ સક્રિય ઇવેન્ટ મળી નથી. કૃપા કરીને સમિતિનો સંપર્ક કરો.",
        "food.no_pending_tokens": "કોઈ પેન્ડિંગ ટોકન ઉપલબ્ધ નથી.",
        "food.no_tokens": "કોઈ ટોકન ઉપલબ્ધ નથી.",
        "food.pending_tokens": "પેન્ડિંગ ટોકન",
        "food.tokens": "ટોકન",
        "food.no_flats_pending": "પેન્ડિંગ ટોકન ધરાવતા ફ્લેટ મળ્યા નથી.",
        "food.flats": "ફ્લેટ્સ",
        "food.select_to_continue": "આગળ વધવા માટે પસંદ કરો",
        "food.verify_header": "ફૂડ ટોકન ચકાસો",
        "food.verify_body": "સર્વ કરવા માટે ટોકન પસંદ કરો",
        "food.scan_header": "ફૂડ QR સ્કેન કરો",
        "food.scan_body": "સ્કેન કરેલ ટોકન પસંદ કરો",
        "food.status_header": "ટોકન સ્થિતિ",
        "food.status_body": "તપાસ માટે ટોકન પસંદ કરો",
        "food.serve_flat_header": "ફ્લેટ સર્વ કરો",
        "food.serve_flat_body": "ફોલબેક સર્વ માટે ફ્લેટ પસંદ કરો",
        "food.flat_passes_header": "ફ્લેટ પાસ",
        "food.flat_passes_body": "સ્થિતિ જોવા માટે ફ્લેટ પસંદ કરો",
        "food.served_token": "✅ ટોકન {token_code} ({food_type}) સર્વ થયું.",
        "food.token_status_line": "🔎 ટોકન {token_code} | {food_type} | {status}",
        "food.flat_not_found": "ફ્લેટ મળ્યો નથી.",
        "food.served_flat": "✅ ટોકન {token_code} થી {flat_number} સર્વ થયું.",
        "food.flat_status_line": "📊 {flat_number} | કુલ {total_passes} | સર્વ {served} | બાકી {remaining}",
        "food.status_served": "સર્વ",
        "food.status_pending": "પેન્ડિંગ",
        "common.error_with_reason": "❌ {error}",
        "participation.pass_updates_active_only": "પાસ અપડેટ્સ ફક્ત ઇવેન્ટ સક્રિય હોય ત્યારે ઉપલબ્ધ છે.",
        "finance.no_outstanding": "ચુકવણી માટે કોઈ બાકી રકમ નથી.",
        "finance.payment_refund_active_only": "ચુકવણી અને રિફંડ વિનંતીઓ ફક્ત સક્રિય ઇવેન્ટ દરમિયાન ઉપલબ્ધ છે.",
        "committee.no_society_context": "સોસાયટી સંદર્ભ મળ્યો નથી.",
        "committee.no_eligible_members_add": "ઉમેરવા માટે કોઈ પાત્ર સભ્ય મળ્યો નથી.",
        "committee.view_none": "કોઈ સમિતિ સભ્ય મળ્યો નથી.",
        "committee.view_header": "સમિતિ સભ્યો:",
        "committee.member_not_found": "સભ્ય મળ્યો નથી.",
        "committee.invalid_role_selection": "અમાન્ય ભૂમિકા પસંદગી.",
        "committee.action_cancelled": "ક્રિયા રદ કરવામાં આવી.",
        "committee.unable_add": "સભ્ય ઉમેરવામાં અસમર્થ.",
        "committee.member_exists": "સભ્ય પહેલેથી જ સમિતિમાં છે.",
        "committee.member_added": "સભ્ય સફળતાપૂર્વક ઉમેરાયો",
        "committee.cannot_remove_last_chairman": "છેલ્લા ચેરમેનને દૂર કરી શકાતા નથી",
        "committee.member_removed": "સભ્ય સફળતાપૂર્વક દૂર થયો",
        "committee.unable_change_role": "ભૂમિકા બદલવામાં અસમર્થ.",
        "committee.role_updated": "સભ્યની ભૂમિકા સફળતાપૂર્વક અપડેટ થઈ",
        "committee.unable_process_action": "સમિતિ ક્રિયા પ્રક્રિયા કરી શકાઈ નહીં.",
        "committee.action.remove": "દૂર કરવું",
        "committee.action.assign_role_to": "ને ભૂમિકા આપવી",
        "committee.action.change_role_for": "માટે ભૂમિકા બદલવી",
    },
}


def _ui_text(lang: str | None, key: str, **params) -> str:
    normalized = normalize_language_code(lang) or "en"
    template = UI_TEXT.get(normalized, UI_TEXT["en"]).get(key, UI_TEXT["en"].get(key, key))
    return template.format(**params) if params else template


def _resolve_sender_language(*, db, sender_id: str) -> str:
    try:
        return resolve_sender_language(db, sender_id=sender_id, channel="whatsapp")
    except Exception:
        return "en"


def _default_report_event_id(event) -> str | None:
    if not event:
        return None
    status = (getattr(event, "status", "") or "").upper()
    if status in REPORT_AUTO_EVENT_STATES:
        return str(event.id)
    return None


def _report_page_option_limit(*, total_options: int, page_size: int = WHATSAPP_LIST_MAX_ROWS) -> int:
    if page_size <= 1:
        return 1
    return page_size - 1 if total_options > page_size else page_size


def _chunk_report_options(options: list[dict], page_size: int = WHATSAPP_LIST_MAX_ROWS) -> list[list[dict]]:
    if page_size <= 0:
        page_size = WHATSAPP_LIST_MAX_ROWS
    return [options[idx : idx + page_size] for idx in range(0, len(options), page_size)]


def _normalize_report_page(page_index: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return page_index % total_pages


def _next_report_page(current_page: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return (current_page + 1) % total_pages




def _get_latest_event_in_context(*, db, society_id, allow_global_fallback: bool = True):
    event = get_latest_event_for_society(db, society_id)
    if event:
        return event
    if not allow_global_fallback:
        return None
    return get_latest_event(db)


def _recent_report_events(*, db, society_id) -> list[Event]:
    if not society_id:
        return []
    cutoff = utc_now() - timedelta(days=365)
    return (
        db.query(Event)
        .filter(Event.society_id == society_id, Event.event_date >= cutoff)
        .order_by(Event.event_date.desc())
        .limit(9)
        .all()
    )


def _build_report_event_sections(events: list[Event]) -> list[dict]:
    rows = [
        {
            "id": f"{WHATSAPP_REPORT_EVENT_ROW_PREFIX}{event.id}",
            "title": (event.name or "Event")[:24],
            "description": f"{event.event_date.strftime('%d %b %Y %H:%M')} · {event.status}",
        }
        for event in events
    ]
    if not rows:
        rows.append(
            {
                "id": "menu",
                "title": "Main Menu",
                "description": "No events found.",
            }
        )
    return [{"title": "Select event", "rows": rows}]


def _parse_report_event_selection(message_text: str) -> str | None:
    text = (message_text or "").strip().lower()
    prefix = WHATSAPP_REPORT_EVENT_ROW_PREFIX
    if not text.startswith(prefix):
        return None
    return text[len(prefix):].strip() or None




def _recent_member_events(*, db, sender_id: str) -> list[Event]:
    normalized_sender = normalize_phone(sender_id)
    if not normalized_sender:
        return []

    candidate_ids = {normalized_sender}
    if len(normalized_sender) > 10:
        candidate_ids.add(normalized_sender[-10:])

    mappings = (
        db.query(UserFlatMapping.society_id)
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(
            MemberIdentity.normalized_identifier.in_(tuple(candidate_ids)),
            UserFlatMapping.is_active.is_(True),
        )
        .distinct()
        .all()
    )
    society_ids = [m.society_id for m in mappings if getattr(m, "society_id", None)]
    if not society_ids:
        return []

    return (
        db.query(Event)
        .filter(Event.society_id.in_(tuple(society_ids)))
        .order_by(Event.event_date.desc())
        .limit(9)
        .all()
    )


def _build_finance_event_sections(events: list[Event]) -> list[dict]:
    rows = [
        {
            "id": f"{WHATSAPP_FINANCE_EVENT_ROW_PREFIX}{event.id}",
            "title": (event.name or "Event")[:24],
            "description": f"{event.event_date.strftime('%d %b %Y %H:%M')} · {event.status}",
        }
        for event in events
    ]
    if not rows:
        rows.append(
            {
                "id": "menu",
                "title": "Main Menu",
                "description": "No events found.",
            }
        )
    return [{"title": "Select event", "rows": rows}]


def _parse_finance_event_selection(message_text: str) -> str | None:
    text = (message_text or "").strip().lower()
    if not text.startswith(WHATSAPP_FINANCE_EVENT_ROW_PREFIX):
        return None
    return text[len(WHATSAPP_FINANCE_EVENT_ROW_PREFIX):].strip() or None


def _select_event_for_finance_action(*, db, sender_id: str, society_id, action: str) -> tuple[Event | None, bool]:
    latest_event = _get_latest_event_in_context(db=db, society_id=society_id)
    if latest_event and str((latest_event.status or "").upper()) in REPORT_AUTO_EVENT_STATES:
        return latest_event, True

    events = _recent_member_events(db=db, sender_id=sender_id)
    if len(events) == 1:
        return events[0], True
    return None, False


def _request_finance_event_selection(*, client, message, db, canonical_sender: str, action: str, lang: str | None = None) -> bool:
    finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
    save_finance_action_session(
        finance_session_key,
        FinanceActionSessionState(pending_action=action, event_id=None),
    )
    events = _recent_member_events(db=db, sender_id=canonical_sender)
    client.send_list_message(
        to_phone=message.sender_id,
        header_text=_ui_text(lang, "finance.select_event_header"),
        body_text=_ui_text(lang, "finance.select_event_body"),
        button_text=_ui_text(lang, "finance.select_event_button"),
        sections=_build_finance_event_sections(events),
    )
    return True

def _is_committee_member(*, db, sender_id: str, external_user_id: str) -> bool:
    try:
        ensure_committee_member(
            sender_id,
            db,
            channel_type="whatsapp",
            external_user_id=external_user_id,
        )
        return True
    except Exception:
        return False


def _get_committee_member(*, db, sender_id: str, external_user_id: str):
    try:
        return ensure_committee_member(
            sender_id,
            db,
            channel_type="whatsapp",
            external_user_id=external_user_id,
        )
    except Exception:
        return None


def _resolve_sender_society_context(*, db, sender_id: str, external_user_id: str):
    committee_member = _get_committee_member(
        db=db,
        sender_id=sender_id,
        external_user_id=external_user_id,
    )
    committee_society_id = getattr(committee_member, "society_id", None) if committee_member else None
    if committee_society_id:
        return committee_society_id, committee_member
    return resolve_sender_society_id(db, sender_id), committee_member if committee_member else None


def _is_registered_member_for_sender(*, db, sender_id: str) -> bool:
    normalized_sender = normalize_phone(sender_id)
    if not normalized_sender:
        return False

    candidate_ids = {normalized_sender}
    if len(normalized_sender) > 10:
        candidate_ids.add(normalized_sender[-10:])

    return (
        db.query(UserFlatMapping.id)
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(
            MemberIdentity.normalized_identifier.in_(tuple(candidate_ids)),
            UserFlatMapping.is_active.is_(True),
        )
        .first()
        is not None
    )


def _resolve_member_identity(*, db, sender_id: str) -> MemberIdentity | None:
    normalized_sender = normalize_phone(sender_id)
    if not normalized_sender:
        return None

    candidate_ids = {normalized_sender}
    if len(normalized_sender) > 10:
        candidate_ids.add(normalized_sender[-10:])

    return (
        db.query(MemberIdentity)
        .filter(
            (MemberIdentity.whatsapp_user_id.in_(tuple(candidate_ids)))
            | (MemberIdentity.normalized_identifier.in_(tuple(candidate_ids)))
            | (MemberIdentity.normalized_phone.in_(tuple(candidate_ids)))
        )
        .first()
    )


def _filter_sections_by_state(*, sections: list[dict], event_state: str | None, is_committee: bool) -> list[dict]:
    keyword_to_intent = {keyword: intent for intent, keyword in WHATSAPP_INTENTS.items()}
    filtered_sections = []
    for section in sections:
        rows = []
        for row in section.get("rows", []):
            row_id = (row.get("id") or "").strip().lower()
            intent = keyword_to_intent.get(row_id)
            if intent and not is_member_action_visible(intent=intent, event_state=event_state, is_committee=is_committee):
                continue
            rows.append(row)
        if rows:
            filtered_sections.append({**section, "rows": rows})
    return filtered_sections




def _with_navigation(
    *,
    sections: list[dict],
    back_id: str | None = None,
    include_main_menu: bool = True,
    lang: str | None = None,
) -> list[dict]:
    nav_rows = []
    if back_id:
        nav_rows.append({"id": back_id, "title": _ui_text(lang, "common.back"), "description": _ui_text(lang, "common.back_description")})
    if include_main_menu:
        nav_rows.append({"id": "menu", "title": _ui_text(lang, "common.main_menu"), "description": _ui_text(lang, "common.main_menu_description")})
    return [*sections, {"title": _ui_text(lang, "common.navigation"), "rows": nav_rows}] if nav_rows else sections


def _get_current_event_state(db, society_id) -> str | None:
    try:
        return get_event_state(_get_latest_event_in_context(db=db, society_id=society_id))
    except Exception:
        return None


def _button_row(row_id: str, title: str) -> dict:
    return {
        "type": "reply",
        "reply": {
            "id": row_id,
            "title": title[:20],
        },
    }


def _send_dashboard_ui(*, client, sender_id: str, is_committee: bool, lang: str | None = None) -> None:
    if is_committee:
        buttons = [
            _button_row("ui::administration", _ui_text(lang, "administration.header")),
            _button_row("ui::reports", "Reports"),
            _button_row("ui::menu:more", "More"),
        ]
    else:
        buttons = [
            _button_row("ui::my-account", "My Account"),
            _button_row("ui::finance", "Finance"),
            _button_row("ui::menu:more", "More"),
        ]

    client.send_button_message(
        to_phone=sender_id,
        header_text=_ui_text(lang, "dashboard.header"),
        body_text=_ui_text(lang, "dashboard.select_action"),
        buttons=buttons,
    )


def _send_dashboard_all_sections(*, client, sender_id: str, is_committee: bool, lang: str | None = None) -> None:
    client.send_list_message(
        to_phone=sender_id,
        header_text=_ui_text(lang, "dashboard.header"),
        body_text=_ui_text(lang, "dashboard.open_all_sections"),
        button_text=_ui_text(lang, "common.open"),
        sections=_with_navigation(sections=build_main_dashboard_sections(is_committee=is_committee, lang=lang), back_id="ui::menu", lang=lang),
    )


def _build_language_sections(*, lang: str | None = None) -> list[dict]:
    return [{
        "title": _ui_text(lang, "language.section_title"),
        "rows": [
            {"id": f"{LANGUAGE_ROW_PREFIX}en", "title": "English", "description": "Receive bot messages in English"},
            {"id": f"{LANGUAGE_ROW_PREFIX}hi", "title": "हिन्दी", "description": "हिन्दी में संदेश पाएँ"},
            {"id": f"{LANGUAGE_ROW_PREFIX}gu", "title": "ગુજરાતી", "description": "ગુજરાતીમાં સંદેશાઓ મેળવો"},
        ],
    }]


def _send_food_token_picker(
    *,
    client,
    sender_id: str,
    db,
    event_id,
    row_prefix: str,
    header: str,
    body: str,
    pending_only: bool = True,
    lang: str | None = None,
) -> bool:
    token_query = db.query(EventFoodToken).filter(EventFoodToken.event_id == event_id)
    if pending_only:
        token_query = token_query.filter(EventFoodToken.served_at.is_(None))

    tokens = token_query.order_by(EventFoodToken.created_at.asc()).limit(8).all()
    if not tokens:
        empty_message = _ui_text(lang, "food.no_pending_tokens") if pending_only else _ui_text(lang, "food.no_tokens")
        client.send_text_message(sender_id, empty_message)
        return True

    rows = [
        {
            "id": f"{row_prefix}{token.token_code}",
            "title": token.token_code,
            "description": f"{token.food_type.title()} | {'Served' if token.served_at else 'Pending'}",
        }
        for token in tokens
    ]
    section_title = _ui_text(lang, "food.pending_tokens") if pending_only else _ui_text(lang, "food.tokens")
    client.send_list_message(
        to_phone=sender_id,
        header_text=header,
        body_text=body,
        button_text=_ui_text(lang, "common.select"),
        sections=_with_navigation(
            sections=[{"title": section_title, "rows": rows}],
            back_id="ui::administration:food",
            lang=lang,
        ),
    )
    return True


def _send_food_flat_picker(*, client, sender_id: str, db, event_id, row_prefix: str, header: str, body: str, lang: str | None = None) -> bool:
    flat_ids = (
        db.query(EventFoodToken.flat_id)
        .filter(
            EventFoodToken.event_id == event_id,
            EventFoodToken.served_at.is_(None),
        )
        .distinct()
        .limit(8)
        .all()
    )
    if not flat_ids:
        client.send_text_message(sender_id, _ui_text(lang, "food.no_flats_pending"))
        return True

    ids = [row[0] for row in flat_ids]
    flats = (
        db.query(Flat)
        .filter(Flat.id.in_(tuple(ids)))
        .order_by(Flat.flat_number.asc())
        .all()
    )
    rows = [
        {
            "id": f"{row_prefix}{flat.flat_number}",
            "title": flat.flat_number,
            "description": _ui_text(lang, "food.select_to_continue"),
        }
        for flat in flats
    ]
    client.send_list_message(
        to_phone=sender_id,
        header_text=header,
        body_text=body,
        button_text=_ui_text(lang, "common.select"),
        sections=_with_navigation(
            sections=[{"title": _ui_text(lang, "food.flats"), "rows": rows}],
            back_id="ui::administration:food",
            lang=lang,
        ),
    )
    return True


def _committee_role_label(role: str) -> str:
    role_map = dict(COMMITTEE_ROLE_OPTIONS)
    return role_map.get(role, role.replace("_", " ").title())


def _build_committee_role_sections(*, include_navigation: bool = True, lang: str | None = None) -> list[dict]:
    sections = [{
        "title": _ui_text(lang, "committee.select_role"),
        "rows": [
            {
                "id": f"{COMMITTEE_ROLE_ROW_PREFIX}{role}",
                "title": label,
                "description": _ui_text(lang, "committee.assign_role", role=label),
            }
            for role, label in COMMITTEE_ROLE_OPTIONS
        ],
    }]
    if include_navigation:
        return _with_navigation(sections=sections, back_id="ui::administration:committee", lang=lang)
    return sections


def _parse_prefixed_row(*, message_text: str, prefix: str) -> str | None:
    text = (message_text or "").strip().lower()
    if not text.startswith(prefix):
        return None
    return text[len(prefix):].strip() or None


def _committee_member_title(member) -> str:
    return (getattr(member, "name", None) or "Member")[:24]


def _committee_member_description(member) -> str:
    phone = getattr(member, "phone_number", "") or ""
    role = _committee_role_label((getattr(member, "role", "") or "").lower())
    return f"{phone} · {role}"[:72]


def _send_committee_member_selection(*, client, sender_id: str, body_text: str, members: list, row_prefix: str, lang: str | None = None) -> None:
    rows = [
        {
            "id": f"{row_prefix}{member.id}",
            "title": _committee_member_title(member),
            "description": _committee_member_description(member),
        }
        for member in members[:8]
    ]
    if not rows:
        rows = [{"id": "ui::administration:committee", "title": _ui_text(lang, "common.back"), "description": _ui_text(lang, "committee.no_members")}]
    client.send_list_message(
        to_phone=sender_id,
        header_text=_ui_text(lang, "committee.header"),
        body_text=body_text,
        button_text=_ui_text(lang, "common.select"),
        sections=_with_navigation(sections=[{"title": _ui_text(lang, "committee.members"), "rows": rows}], back_id="ui::administration:committee", lang=lang),
    )


def _send_add_member_selection(*, client, sender_id: str, db, society_id, lang: str | None = None) -> bool:
    if not society_id:
        client.send_text_message(sender_id, _ui_text(lang, "committee.no_society_context"))
        return True

    existing_numbers = {
        (member.phone_number or "").strip()
        for member in db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True)).all()
    }
    mappings = (
        db.query(UserFlatMapping, MemberIdentity)
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(UserFlatMapping.society_id == society_id, UserFlatMapping.is_active.is_(True))
        .all()
    )

    rows = []
    seen_ids = set()
    for _mapping, identity in mappings:
        identifier = (getattr(identity, "normalized_identifier", "") or "").strip()
        if not identifier or identifier in existing_numbers or identity.id in seen_ids:
            continue
        seen_ids.add(identity.id)
        rows.append({
            "id": f"{COMMITTEE_ADD_MEMBER_ROW_PREFIX}{identity.id}",
            "title": (identifier[-10:] if len(identifier) > 10 else identifier)[:24],
            "description": _ui_text(lang, "committee.select_member_to_add"),
        })
        if len(rows) >= 8:
            break

    if not rows:
        client.send_text_message(sender_id, _ui_text(lang, "committee.no_eligible_members_add"))
        return True

    client.send_list_message(
        to_phone=sender_id,
        header_text=_ui_text(lang, "committee.add_header"),
        body_text=_ui_text(lang, "committee.choose_member"),
        button_text=_ui_text(lang, "common.select"),
        sections=_with_navigation(
            sections=[{"title": _ui_text(lang, "committee.society_members"), "rows": rows}],
            back_id="ui::administration:committee",
            lang=lang,
        ),
    )
    return True


def _handle_committee_view(*, client, sender_id: str, db, society_id, lang: str | None = None) -> bool:
    members = (
        db.query(CommitteeMember)
        .filter(CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True))
        .order_by(CommitteeMember.role.asc(), CommitteeMember.name.asc())
        .all()
    )
    if not members:
        client.send_text_message(sender_id, _ui_text(lang, "committee.view_none"))
        return True

    lines = [_ui_text(lang, "committee.view_header")]
    for member in members:
        lines.append(f"- {_committee_member_title(member)} ({_committee_role_label((member.role or '').lower())})")
    client.send_text_message(sender_id, "\n".join(lines))
    return True


def _send_committee_confirmation(*, client, sender_id: str, action: str, member_label: str, role_label: str | None = None, lang: str | None = None) -> None:
    role_suffix = f" as {role_label}" if role_label else ""
    client.send_list_message(
        to_phone=sender_id,
        header_text=_ui_text(lang, "committee.confirm_header"),
        body_text=_ui_text(lang, "committee.confirm_body", action=action, member=member_label, role_suffix=role_suffix),
        button_text=_ui_text(lang, "common.confirm"),
        sections=_with_navigation(
            sections=[
                {
                    "title": _ui_text(lang, "committee.confirm_section"),
                    "rows": [
                        {"id": f"{COMMITTEE_CONFIRM_ROW_PREFIX}yes", "title": _ui_text(lang, "committee.confirm_yes"), "description": _ui_text(lang, "committee.confirm_yes_description")},
                        {"id": f"{COMMITTEE_CONFIRM_ROW_PREFIX}no", "title": _ui_text(lang, "committee.confirm_no"), "description": _ui_text(lang, "committee.confirm_no_description")},
                    ],
                }
            ],
            back_id="ui::administration:committee",
            lang=lang,
        ),
    )





def _try_handle_ui_message(*, client, message) -> bool:
    msg = message.text.strip().lower()

    canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
    membership_gated_ui_ids = {
        "ui::menu",
        "ui::menu:more",
        "ui::my-account",
        "ui::society",
        "ui::finance",
        "ui::payments",
        "ui::participation",
        "ui::language",
        "ui::reports",
        "ui::administration",
        "ui::administration:approvals",
        "ui::administration:operations",
        "ui::administration:operations:more",
        "ui::administration:food",
        "ui::administration:reports",
        "ui::administration:committee",
        "committee::view",
        "committee::add",
        "committee::remove",
        "committee::change-role",
    }
    if msg in membership_gated_ui_ids:
        db = SessionLocal()
        try:
            try:
                society_id, committee_member = _resolve_sender_society_context(
                    db=db,
                    sender_id=canonical_sender,
                    external_user_id=message.sender_id,
                )
                latest_event = _get_latest_event_in_context(db=db, society_id=society_id, allow_global_fallback=False)
                is_committee = committee_member is not None
                is_society_member = None if not is_committee else False
                if not is_committee:
                    try:
                        is_society_member = _is_registered_member_for_sender(
                            db=db,
                            sender_id=canonical_sender,
                        )
                    except Exception:
                        is_society_member = None
                if latest_event and not is_committee and is_society_member is not True:
                    try:
                        resolve_flat(
                            db,
                            phone_number=canonical_sender,
                            society_id=latest_event.society_id,
                        )
                        is_society_member = True
                    except Exception:
                        try:
                            ensure_member_of_society(canonical_sender, db, latest_event.society_id)
                            is_society_member = True
                        except Exception:
                            is_society_member = False

                if not is_committee and is_society_member is False:
                    lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
                    client.send_button_message(
                        to_phone=message.sender_id,
                        header_text=_ui_text(lang, "registration.header"),
                        body_text=_ui_text(lang, "registration.body"),
                        buttons=[_button_row("ui::join-society", _ui_text(lang, "registration.join"))],
                    )
                    return True
            except Exception:
                logger.exception("Failed pre-check for WhatsApp UI registration gate")
        finally:
            db.close()

    if msg in {"menu", "help", "ui::menu", "ui::menu:more"}:
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(
                db=db,
                sender_id=canonical_sender,
                external_user_id=message.sender_id,
            )
            latest_event = _get_latest_event_in_context(db=db, society_id=society_id, allow_global_fallback=False)
            is_committee = committee_member is not None
            is_society_member = None if not is_committee else False
            if not is_committee:
                try:
                    is_society_member = _is_registered_member_for_sender(
                        db=db,
                        sender_id=canonical_sender,
                    )
                except Exception:
                    is_society_member = None
            if latest_event and not is_committee and is_society_member is not True:
                try:
                    resolve_flat(
                        db,
                        phone_number=canonical_sender,
                        society_id=latest_event.society_id,
                    )
                    is_society_member = True
                except Exception:
                    try:
                        ensure_member_of_society(canonical_sender, db, latest_event.society_id)
                        is_society_member = True
                    except Exception:
                        is_society_member = False

            if msg in {"menu", "help"} and not is_committee and is_society_member is False:
                lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
                client.send_button_message(
                    to_phone=message.sender_id,
                    header_text=_ui_text(lang, "registration.header"),
                    body_text=_ui_text(lang, "registration.body"),
                    buttons=[_button_row("ui::join-society", _ui_text(lang, "registration.join"))],
                )
                return True

            requires_event_context = msg == "ui::menu:more"
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            if requires_event_context and not latest_event:
                _send_dashboard_all_sections(
                    client=client,
                    sender_id=message.sender_id,
                    is_committee=False,
                    lang=lang,
                )
                return True

            if msg == "ui::menu:more":
                _send_dashboard_all_sections(
                    client=client,
                    sender_id=message.sender_id,
                    is_committee=is_committee,
                    lang=lang,
                )
                return True

            _send_dashboard_ui(
                client=client,
                sender_id=message.sender_id,
                is_committee=is_committee,
                lang=lang,
            )
            return True
        finally:
            db.close()

    if msg == "ui::participation":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            can_add_pass = is_member_action_visible(intent="ADD_PASS", event_state=event_state, is_committee=is_committee)
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text=_ui_text(lang, "participation.header"),
                body_text=_ui_text(lang, "participation.body"),
                button_text=_ui_text(lang, "common.open"),
                sections=_with_navigation(sections=build_participation_sections(include_add_pass=can_add_pass), back_id="ui::my-account", lang=lang),
            )
            return True
        finally:
            db.close()

    if msg == "ui::participation:add-update-pass":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            if not is_member_action_visible(intent="ADD_PASS", event_state=event_state, is_committee=is_committee):
                client.send_text_message(message.sender_id, _ui_text(lang, "participation.pass_updates_active_only"))
                return True
        finally:
            db.close()
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="ADD_PASS_COUNTS"),
        )
        client.send_text_message(message.sender_id, add_or_update_pass_prompt())
        return True

    if msg == "ui::payments":
        db = SessionLocal()
        try:
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
        finally:
            db.close()
        client.send_list_message(
            to_phone=message.sender_id,
            header_text=_ui_text(lang, "payments.header"),
            body_text=_ui_text(lang, "payments.body"),
            button_text=_ui_text(lang, "common.open"),
            sections=_with_navigation(sections=build_payments_sections(), back_id="ui::finance", lang=lang),
        )
        return True

    if msg == "ui::finance:view-balance":
        db = SessionLocal()
        try:
            finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
            finance_session = get_finance_action_session(finance_session_key)
            society_id, _committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            selected_event = None
            if finance_session and finance_session.pending_action == "VIEW_BALANCE" and finance_session.event_id:
                selected_event = db.query(Event).filter(Event.id == finance_session.event_id).first()
            if not selected_event:
                selected_event, _ = _select_event_for_finance_action(
                    db=db,
                    sender_id=canonical_sender,
                    society_id=society_id,
                    action="VIEW_BALANCE",
                )
            if not selected_event:
                lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
                return _request_finance_event_selection(
                    client=client,
                    message=message,
                    db=db,
                    canonical_sender=canonical_sender,
                    action="VIEW_BALANCE",
                    lang=lang,
                )
            flat = resolve_flat(db, phone_number=canonical_sender, society_id=selected_event.society_id)
            balance = UserQueryService.get_my_balance(db=db, event_id=selected_event.id, flat_id=flat.id)
            summary = UserQueryService.get_my_payment_summary(db=db, event_id=selected_event.id, flat_id=flat.id)
            client.send_text_message(
                message.sender_id,
                format_financial_overview(
                    expected=format_currency(balance["expected"]),
                    paid=format_currency(balance["paid"]),
                    refunded=format_currency(summary["refunded"]),
                    outstanding=format_currency(balance["balance"]),
                ),
            )
            if finance_session and finance_session.pending_action == "VIEW_BALANCE":
                clear_finance_action_session(finance_session_key)
            return True
        except Exception:
            logger.exception("Failed to build financial overview")
            return False
        finally:
            db.close()

    if msg == "ui::make-payment":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
            finance_session = get_finance_action_session(finance_session_key)
            selected_event = None
            if finance_session and finance_session.pending_action == "MAKE_PAYMENT" and finance_session.event_id:
                selected_event = db.query(Event).filter(Event.id == finance_session.event_id).first()
            if not selected_event:
                selected_event, _ = _select_event_for_finance_action(
                    db=db,
                    sender_id=canonical_sender,
                    society_id=society_id,
                    action="MAKE_PAYMENT",
                )
            if not selected_event:
                return _request_finance_event_selection(
                    client=client,
                    message=message,
                    db=db,
                    canonical_sender=canonical_sender,
                    action="MAKE_PAYMENT",
                    lang=lang,
                )
            flat = resolve_flat(db, phone_number=canonical_sender, society_id=selected_event.society_id)
            balance = UserQueryService.get_my_balance(db=db, event_id=selected_event.id, flat_id=flat.id)
            outstanding = balance.get("balance", 0)
            if outstanding <= 0:
                client.send_text_message(message.sender_id, _ui_text(lang, "finance.no_outstanding"))
                return True
            client.send_list_message(
                to_phone=message.sender_id,
                header_text=_ui_text(lang, "make_payment.header"),
                body_text=_ui_text(lang, "make_payment.outstanding_body", amount=format_currency(outstanding)),
                button_text=_ui_text(lang, "common.select"),
                sections=build_make_payment_sections(outstanding_amount=str(int(outstanding) if float(outstanding).is_integer() else outstanding)),
            )
            if finance_session and finance_session.pending_action == "MAKE_PAYMENT":
                clear_finance_action_session(finance_session_key)
            return True
        except Exception:
            logger.exception("Failed to build make payment menu")
            return False
        finally:
            db.close()

    if msg == "ui::finance:pay-custom":
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="PAY_CUSTOM"),
        )
        client.send_text_message(message.sender_id, payment_custom_amount_prompt())
        return True

    if msg == "ui::request-refund":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            if not is_member_action_visible(intent="REFUND", event_state=event_state, is_committee=is_committee):
                client.send_text_message(message.sender_id, _ui_text(lang, "finance.payment_refund_active_only"))
                return True
        finally:
            db.close()
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="REFUND_REQUEST"),
        )
        client.send_text_message(message.sender_id, refund_request_prompt())
        return True

    if msg == "ui::my-account":
        db = SessionLocal()
        try:
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
        finally:
            db.close()
        client.send_list_message(
            to_phone=message.sender_id,
            header_text=_ui_text(lang, "my_account.header"),
            body_text=_ui_text(lang, "my_account.body"),
            button_text=_ui_text(lang, "common.open"),
            sections=_with_navigation(sections=build_my_account_sections(lang=lang), back_id="ui::menu", lang=lang),
        )
        return True

    if msg == "ui::language":
        db = SessionLocal()
        try:
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
        finally:
            db.close()
        client.send_list_message(
            to_phone=message.sender_id,
            header_text=_ui_text(lang, "language.section_title"),
            body_text=_ui_text(lang, "language.choose_body"),
            button_text=_ui_text(lang, "common.select"),
            sections=_with_navigation(sections=_build_language_sections(lang=lang), back_id="ui::my-account", lang=lang),
        )
        return True

    if msg == "ui::society":
        db = SessionLocal()
        try:
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
        finally:
            db.close()
        client.send_list_message(
            to_phone=message.sender_id,
            header_text=_ui_text(lang, "society.header"),
            body_text=_ui_text(lang, "society.body"),
            button_text=_ui_text(lang, "common.open"),
            sections=_with_navigation(sections=build_society_sections(lang=lang), back_id="ui::menu", lang=lang),
        )
        return True

    if msg == "ui::join-society":
        db = SessionLocal()
        try:
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
        finally:
            db.close()
        session_key = build_join_session_key(sender_id=message.sender_id)
        save_join_session(
            session_key,
            JoinSessionState(pending_action="JOIN"),
        )
        client.send_text_message(message.sender_id, _ui_text(lang, "join.enter_code"))
        return True

    selected_language = _parse_prefixed_row(message_text=msg, prefix=LANGUAGE_ROW_PREFIX)
    if selected_language:
        db = SessionLocal()
        try:
            identity = _resolve_member_identity(db=db, sender_id=canonical_sender)
            if identity is None:
                identity = MemberIdentityService.resolve_or_create(db, user_identifier=canonical_sender)
            normalized_language = set_preferred_language(
                db,
                identity=identity,
                language_code=selected_language,
            )
            client.send_text_message(
                message.sender_id,
                _ui_text(normalized_language, "language.updated"),
            )
            return True
        except ValueError:
            client.send_text_message(
                message.sender_id,
                _ui_text(_resolve_sender_language(db=db, sender_id=canonical_sender), "language.unsupported"),
            )
            return True
        finally:
            db.close()

    if msg == "ui::finance":
        db = SessionLocal()
        try:
            society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            event_state = _get_current_event_state(db, society_id)
            can_use_payment = is_member_action_visible(intent="PAY", event_state=event_state, is_committee=is_committee)
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text=_ui_text(lang, "finance.header"),
                body_text=_ui_text(lang, "finance.body"),
                button_text=_ui_text(lang, "common.open"),
                sections=_with_navigation(sections=build_finance_sections(include_payment_actions=can_use_payment, lang=lang), back_id="ui::menu", lang=lang),
            )
            return True
        finally:
            db.close()

    if msg == "ui::reports":
        db = SessionLocal()
        try:
            _society_id, committee_member = _resolve_sender_society_context(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            is_committee = committee_member is not None
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            sections = build_reports_sections(is_committee=is_committee, lang=lang)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text=_ui_text(lang, "reports.header"),
                body_text=_ui_text(lang, "reports.select_action"),
                button_text=_ui_text(lang, "common.open"),
                sections=_with_navigation(sections=sections, back_id="ui::menu", lang=lang),
            )
            return True
        finally:
            db.close()

    if msg in {"ui::administration", "ui::administration:approvals", "ui::administration:operations", "ui::administration:operations:more", "ui::administration:reports", "ui::administration:committee", "ui::administration:food"}:
        db = SessionLocal()
        try:
            member = _get_committee_member(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            if not member:
                lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
                client.send_text_message(message.sender_id, _ui_text(lang, "access.restricted"))
                return True
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            if msg == "ui::administration:approvals":
                base_sections = build_committee_approvals_sections()
                back_id = "ui::administration"
                body_text = _ui_text(lang, "administration.approvals")
            elif msg == "ui::administration:operations":
                base_sections = build_committee_operations_sections()
                back_id = "ui::administration"
                body_text = _ui_text(lang, "administration.operations")
            elif msg == "ui::administration:operations:more":
                base_sections = build_committee_operations_more_sections()
                back_id = "ui::administration:operations"
                body_text = _ui_text(lang, "administration.operations_more")
            elif msg == "ui::administration:reports":
                base_sections = build_committee_reports_sections()
                back_id = "ui::administration"
                body_text = _ui_text(lang, "administration.reports")
            elif msg == "ui::administration:food":
                base_sections = build_committee_food_collection_sections()
                back_id = "ui::administration:operations:more"
                body_text = _ui_text(lang, "administration.food")
            elif msg == "ui::administration:committee":
                base_sections = build_committee_management_sections()
                back_id = "ui::administration"
                body_text = _ui_text(lang, "administration.committee")
            else:
                base_sections = build_committee_sections()
                back_id = "ui::menu"
                body_text = _ui_text(lang, "administration.select_area")

            sections = base_sections
            client.send_list_message(
                to_phone=message.sender_id,
                header_text=_ui_text(lang, "administration.header"),
                body_text=body_text,
                button_text=_ui_text(lang, "common.open"),
                sections=_with_navigation(
                    sections=sections,
                    back_id=back_id,
                    include_main_menu=True,
                    lang=lang,
                ),
            )
            return True
        finally:
            db.close()

    if msg in {"verify food token", "scan food qr", "token status", "serve flat", "flat passes"} or msg.startswith(FOOD_VERIFY_TOKEN_ROW_PREFIX) or msg.startswith(FOOD_SCAN_QR_ROW_PREFIX) or msg.startswith(FOOD_TOKEN_STATUS_ROW_PREFIX) or msg.startswith(FOOD_SERVE_FLAT_ROW_PREFIX) or msg.startswith(FOOD_FLAT_STATUS_ROW_PREFIX):
        db = SessionLocal()
        try:
            member = _get_committee_member(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            if not member:
                lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
                client.send_text_message(message.sender_id, _ui_text(lang, "access.restricted"))
                return True

            event = get_latest_event_for_society(db, member.society_id)
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            if not event:
                client.send_text_message(message.sender_id, _ui_text(lang, "event.none_contact_committee"))
                return True

            if msg == "verify food token":
                return _send_food_token_picker(
                    client=client,
                    sender_id=message.sender_id,
                    db=db,
                    event_id=event.id,
                    row_prefix=FOOD_VERIFY_TOKEN_ROW_PREFIX,
                    header=_ui_text(lang, "food.verify_header"),
                    body=_ui_text(lang, "food.verify_body"),
                    lang=lang,
                )
            if msg == "scan food qr":
                return _send_food_token_picker(
                    client=client,
                    sender_id=message.sender_id,
                    db=db,
                    event_id=event.id,
                    row_prefix=FOOD_SCAN_QR_ROW_PREFIX,
                    header=_ui_text(lang, "food.scan_header"),
                    body=_ui_text(lang, "food.scan_body"),
                    lang=lang,
                )
            if msg == "token status":
                return _send_food_token_picker(
                    client=client,
                    sender_id=message.sender_id,
                    db=db,
                    event_id=event.id,
                    row_prefix=FOOD_TOKEN_STATUS_ROW_PREFIX,
                    header=_ui_text(lang, "food.status_header"),
                    body=_ui_text(lang, "food.status_body"),
                    pending_only=False,
                    lang=lang,
                )
            if msg == "serve flat":
                return _send_food_flat_picker(
                    client=client,
                    sender_id=message.sender_id,
                    db=db,
                    event_id=event.id,
                    row_prefix=FOOD_SERVE_FLAT_ROW_PREFIX,
                    header=_ui_text(lang, "food.serve_flat_header"),
                    body=_ui_text(lang, "food.serve_flat_body"),
                    lang=lang,
                )
            if msg == "flat passes":
                return _send_food_flat_picker(
                    client=client,
                    sender_id=message.sender_id,
                    db=db,
                    event_id=event.id,
                    row_prefix=FOOD_FLAT_STATUS_ROW_PREFIX,
                    header=_ui_text(lang, "food.flat_passes_header"),
                    body=_ui_text(lang, "food.flat_passes_body"),
                    lang=lang,
                )

            selected_token = _parse_prefixed_row(message_text=msg, prefix=FOOD_VERIFY_TOKEN_ROW_PREFIX)
            if selected_token:
                served = FoodCollectionService.verify_and_serve_token(
                    db=db,
                    event_id=event.id,
                    token_code=selected_token,
                    method="MANUAL_TOKEN",
                    performed_by=member.id,
                )
                client.send_text_message(
                    message.sender_id,
                    _ui_text(lang, "food.served_token", token_code=served.token_code, food_type=served.food_type),
                )
                return True

            selected_token = _parse_prefixed_row(message_text=msg, prefix=FOOD_SCAN_QR_ROW_PREFIX)
            if selected_token:
                served = FoodCollectionService.verify_and_serve_token(
                    db=db,
                    event_id=event.id,
                    token_code=selected_token,
                    method="QR_SCAN",
                    performed_by=member.id,
                )
                client.send_text_message(
                    message.sender_id,
                    _ui_text(lang, "food.served_token", token_code=served.token_code, food_type=served.food_type),
                )
                return True

            selected_token = _parse_prefixed_row(message_text=msg, prefix=FOOD_TOKEN_STATUS_ROW_PREFIX)
            if selected_token:
                token = FoodCollectionService.inspect_token(db=db, event_id=event.id, token_code=selected_token)
                status = _ui_text(lang, "food.status_served") if token.served_at else _ui_text(lang, "food.status_pending")
                client.send_text_message(
                    message.sender_id,
                    _ui_text(lang, "food.token_status_line", token_code=token.token_code, food_type=token.food_type, status=status),
                )
                return True

            selected_flat = _parse_prefixed_row(message_text=msg, prefix=FOOD_SERVE_FLAT_ROW_PREFIX)
            if selected_flat:
                flat = db.query(Flat).filter(Flat.society_id == member.society_id, Flat.flat_number == selected_flat).first()
                if not flat:
                    client.send_text_message(message.sender_id, _ui_text(lang, "food.flat_not_found"))
                    return True
                served = FoodCollectionService.serve_by_flat_lookup(
                    db=db,
                    event_id=event.id,
                    flat_id=flat.id,
                    performed_by=member.id,
                )
                client.send_text_message(
                    message.sender_id,
                    _ui_text(lang, "food.served_flat", flat_number=flat.flat_number, token_code=served.token_code),
                )
                return True

            selected_flat = _parse_prefixed_row(message_text=msg, prefix=FOOD_FLAT_STATUS_ROW_PREFIX)
            if selected_flat:
                summary = FoodCollectionService.committee_flat_status(
                    db=db,
                    event_id=event.id,
                    flat_number=selected_flat,
                )
                client.send_text_message(
                    message.sender_id,
                    _ui_text(
                        lang,
                        "food.flat_status_line",
                        flat_number=summary["flat_number"],
                        total_passes=summary["total_passes"],
                        served=summary["served"],
                        remaining=summary["remaining"],
                    ),
                )
                return True
        except Exception as exc:
            client.send_text_message(message.sender_id, _ui_text(lang, "common.error_with_reason", error=exc))
            return True
        finally:
            db.close()


    if msg == "ui::approve-user":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            return _send_approval_selection_list(
                client=client,
                sender_id=message.sender_id,
                approval_type="user",
                db=db,
                canonical_sender=canonical_sender,
                external_user_id=message.sender_id,
            )
        finally:
            db.close()

    if msg == "ui::approve-payment":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            return _send_approval_selection_list(
                client=client,
                sender_id=message.sender_id,
                approval_type="payment",
                db=db,
                canonical_sender=canonical_sender,
                external_user_id=message.sender_id,
            )
        finally:
            db.close()

    if msg == "ui::approve-refund":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            return _send_approval_selection_list(
                client=client,
                sender_id=message.sender_id,
                approval_type="refund",
                db=db,
                canonical_sender=canonical_sender,
                external_user_id=message.sender_id,
            )
        finally:
            db.close()


    if msg in {"committee::view", "committee::add", "committee::remove", "committee::change-role"} or msg.startswith(COMMITTEE_ADD_MEMBER_ROW_PREFIX) or msg.startswith(COMMITTEE_MEMBER_ROW_PREFIX) or msg.startswith(COMMITTEE_ROLE_ROW_PREFIX) or msg.startswith(COMMITTEE_CONFIRM_ROW_PREFIX):
        db = SessionLocal()
        try:
            member = _get_committee_member(db=db, sender_id=canonical_sender, external_user_id=message.sender_id)
            if not member:
                lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
                client.send_text_message(message.sender_id, _ui_text(lang, "access.restricted"))
                return True

            society_id = getattr(member, "society_id", None)
            lang = _resolve_sender_language(db=db, sender_id=canonical_sender)
            session_key = build_committee_management_session_key(sender_id=message.sender_id)
            session_state = get_committee_management_session(session_key)

            if msg == "committee::view":
                clear_committee_management_session(session_key)
                return _handle_committee_view(client=client, sender_id=message.sender_id, db=db, society_id=society_id, lang=lang)

            if msg == "committee::add":
                save_committee_management_session(session_key, CommitteeManagementSessionState(pending_action="ADD"))
                return _send_add_member_selection(client=client, sender_id=message.sender_id, db=db, society_id=society_id, lang=lang)

            if msg == "committee::remove":
                save_committee_management_session(session_key, CommitteeManagementSessionState(pending_action="REMOVE"))
                target_members = db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True)).order_by(CommitteeMember.name.asc()).all()
                _send_committee_member_selection(client=client, sender_id=message.sender_id, body_text=_ui_text(lang, "committee.choose_member_remove"), members=target_members, row_prefix=COMMITTEE_MEMBER_ROW_PREFIX, lang=lang)
                return True

            if msg == "committee::change-role":
                save_committee_management_session(session_key, CommitteeManagementSessionState(pending_action="CHANGE_ROLE"))
                target_members = db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True)).order_by(CommitteeMember.name.asc()).all()
                _send_committee_member_selection(client=client, sender_id=message.sender_id, body_text=_ui_text(lang, "committee.choose_member_update"), members=target_members, row_prefix=COMMITTEE_MEMBER_ROW_PREFIX, lang=lang)
                return True

            selected_identity_id = _parse_prefixed_row(message_text=msg, prefix=COMMITTEE_ADD_MEMBER_ROW_PREFIX)
            if selected_identity_id and session_state and session_state.pending_action == "ADD":
                session_state.selected_member_id = selected_identity_id
                save_committee_management_session(session_key, session_state)
                client.send_list_message(
                    to_phone=message.sender_id,
                    header_text=_ui_text(lang, "committee.add_header"),
                    body_text=_ui_text(lang, "committee.choose_role"),
                    button_text=_ui_text(lang, "common.select"),
                    sections=_build_committee_role_sections(lang=lang),
                )
                return True

            selected_member_id = _parse_prefixed_row(message_text=msg, prefix=COMMITTEE_MEMBER_ROW_PREFIX)
            if selected_member_id and session_state and session_state.pending_action in {"REMOVE", "CHANGE_ROLE"}:
                target = db.query(CommitteeMember).filter(CommitteeMember.id == selected_member_id, CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True)).first()
                if not target:
                    client.send_text_message(message.sender_id, _ui_text(lang, "committee.member_not_found"))
                    return True
                session_state.selected_member_id = str(target.id)
                save_committee_management_session(session_key, session_state)
                if session_state.pending_action == "REMOVE":
                    _send_committee_confirmation(
                        client=client,
                        sender_id=message.sender_id,
                        action=_ui_text(lang, "committee.action.remove"),
                        member_label=_committee_member_title(target),
                        lang=lang,
                    )
                else:
                    client.send_list_message(
                        to_phone=message.sender_id,
                        header_text=_ui_text(lang, "committee.change_role_header"),
                        body_text=_ui_text(lang, "committee.choose_new_role"),
                        button_text=_ui_text(lang, "common.select"),
                        sections=_build_committee_role_sections(lang=lang),
                    )
                return True

            selected_role = _parse_prefixed_row(message_text=msg, prefix=COMMITTEE_ROLE_ROW_PREFIX)
            if selected_role and session_state and session_state.pending_action in {"ADD", "CHANGE_ROLE"}:
                allowed_roles = {role for role, _label in COMMITTEE_ROLE_OPTIONS}
                if selected_role not in allowed_roles:
                    client.send_text_message(message.sender_id, _ui_text(lang, "committee.invalid_role_selection"))
                    return True
                session_state.selected_role = selected_role
                save_committee_management_session(session_key, session_state)
                if session_state.pending_action == "ADD":
                    identity = db.query(MemberIdentity).filter(MemberIdentity.id == session_state.selected_member_id).first()
                    member_label = getattr(identity, "normalized_identifier", "member") if identity else "member"
                else:
                    target = db.query(CommitteeMember).filter(CommitteeMember.id == session_state.selected_member_id).first()
                    member_label = _committee_member_title(target) if target else "member"
                _send_committee_confirmation(
                    client=client,
                    sender_id=message.sender_id,
                    action=(
                        _ui_text(lang, "committee.action.assign_role_to")
                        if session_state.pending_action == "ADD"
                        else _ui_text(lang, "committee.action.change_role_for")
                    ),
                    member_label=member_label,
                    role_label=_committee_role_label(selected_role),
                    lang=lang,
                )
                return True

            confirm_choice = _parse_prefixed_row(message_text=msg, prefix=COMMITTEE_CONFIRM_ROW_PREFIX)
            if confirm_choice and session_state:
                if confirm_choice != "yes":
                    clear_committee_management_session(session_key)
                    client.send_text_message(message.sender_id, _ui_text(lang, "committee.action_cancelled"))
                    return True

                if session_state.pending_action == "ADD":
                    identity = db.query(MemberIdentity).filter(MemberIdentity.id == session_state.selected_member_id).first()
                    if not identity or not session_state.selected_role:
                        clear_committee_management_session(session_key)
                        client.send_text_message(message.sender_id, _ui_text(lang, "committee.unable_add"))
                        return True
                    identifier = (identity.normalized_phone or identity.normalized_identifier or "").strip()
                    existing = db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id, CommitteeMember.phone_number == identifier, CommitteeMember.is_active.is_(True)).first()
                    if existing:
                        clear_committee_management_session(session_key)
                        client.send_text_message(message.sender_id, _ui_text(lang, "committee.member_exists"))
                        return True
                    new_member = CommitteeMember(
                        society_id=society_id,
                        name=identifier,
                        phone_number=identifier,
                        role=session_state.selected_role,
                        is_active=True,
                    )
                    db.add(new_member)
                    db.commit()
                    clear_committee_management_session(session_key)
                    client.send_text_message(message.sender_id, _ui_text(lang, "committee.member_added"))
                    return True

                if session_state.pending_action == "REMOVE":
                    target = db.query(CommitteeMember).filter(CommitteeMember.id == session_state.selected_member_id, CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True)).first()
                    if not target:
                        clear_committee_management_session(session_key)
                        client.send_text_message(message.sender_id, _ui_text(lang, "committee.member_not_found"))
                        return True
                    if (target.role or "").lower() == "chairman":
                        chairman_count = db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True), CommitteeMember.role == "chairman").count()
                        if chairman_count <= 1:
                            clear_committee_management_session(session_key)
                            client.send_text_message(message.sender_id, _ui_text(lang, "committee.cannot_remove_last_chairman"))
                            return True
                    setattr(target, "is_active", False)
                    db.commit()
                    clear_committee_management_session(session_key)
                    client.send_text_message(message.sender_id, _ui_text(lang, "committee.member_removed"))
                    return True

                if session_state.pending_action == "CHANGE_ROLE":
                    target = db.query(CommitteeMember).filter(CommitteeMember.id == session_state.selected_member_id, CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True)).first()
                    if not target or not session_state.selected_role:
                        clear_committee_management_session(session_key)
                        client.send_text_message(message.sender_id, _ui_text(lang, "committee.unable_change_role"))
                        return True
                    if (target.role or "").lower() == "chairman" and session_state.selected_role != "chairman":
                        chairman_count = db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id, CommitteeMember.is_active.is_(True), CommitteeMember.role == "chairman").count()
                        if chairman_count <= 1:
                            clear_committee_management_session(session_key)
                            client.send_text_message(message.sender_id, _ui_text(lang, "committee.cannot_remove_last_chairman"))
                            return True
                    setattr(target, "role", session_state.selected_role)
                    db.commit()
                    clear_committee_management_session(session_key)
                    client.send_text_message(message.sender_id, _ui_text(lang, "committee.role_updated"))
                    return True

            return False
        except Exception:
            logger.exception("Failed committee management flow")
            client.send_text_message(message.sender_id, _ui_text(lang, "committee.unable_process_action"))
            return True
        finally:
            db.close()

    return False
