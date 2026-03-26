from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.users.language_service import DEFAULT_LANGUAGE, normalize_language_code

CatalogValue = str | Mapping[str, "CatalogValue"]
CatalogDict = dict[str, CatalogValue]

TRANSLATIONS: dict[str, CatalogDict] = {
    "en": {
        "dashboard": {
            "sections_title": "Sections",
            "main": {
                "my_account": {"title": "My Account", "description": "Check participation, dues, and support"},
                "society": {"title": "Society", "description": "Join your society and track membership"},
                "finance": {"title": "Finance", "description": "Track dues & refunds"},
                "reports": {"title": "Reports", "description": "View society reports"},
                "administration": {"title": "Administration", "description": "Manage approvals and event operations"},
            },
            "my_account": {
                "participation_section": "Participation",
                "finance_section": "Finance",
                "account_section": "My Account",
                "participation": {"title": "Participation", "description": "Check pass and event status"},
                "event_status": {"title": "Event Status", "description": "View your current event standing"},
                "payments": {"title": "Payments", "description": "Track balance, history, and refunds"},
                "language": {"title": "Language", "description": "Change WhatsApp language"},
                "help": {"title": "Help", "description": "Get guidance on what to send"},
                "menu": {"title": "Main Menu", "description": "Open dashboard again"},
            },
            "society": {
                "section_title": "Society",
                "join_society": {"title": "Join Society", "description": "Start your membership request"},
                "send_join_request": {"title": "Send Join Request", "description": "Send: join <join_code> <flat>"},
                "join_status": {"title": "Join Status", "description": "Track your request"},
            },
            "finance_sections": {
                "section_title": "Finance",
                "payments": {"title": "Payments", "description": "View balance, history, and refund requests"},
                "make_payment": {"title": "Make Payment", "description": "Pay your outstanding dues"},
                "request_refund": {"title": "Request Refund", "description": "Start a new refund request"},
                "pay_dues": {"title": "Pay Dues", "description": "Send: pay <amount>"},
                "refund": {"title": "Request a Refund", "description": "Send: refund <amount> <reason>"},
            },
        },
        "reports": {
            "intro": "Select a report to export. PDF is default.",
            "section_title": "Reports",
            "summary": {"title": "Summary", "description": "Overall event summary"},
            "block_report": {"title": "Block Report", "description": "Building-wise breakdown"},
            "report_options": {"title": "Report Options", "description": "Browse exportable reports"},
            "participation_report": {"title": "Participation Report", "description": "Committee analytics report"},
        },
        "response_templates": {
            "exportable_report_options_heading": "Exportable Report Options",
            "no_exportable_reports": "No exportable reports are configured.",
            "category": "Category",
            "report_key": "Report key",
            "label": "Label",
            "formats": "Formats",
            "example": "Example",
            "report_options_intro": "Select a report event and export option.",
            "not_available": "N/A",
            "main_menu": "Main Menu",
            "help": "Help",
            "report_options": "Report Options",
            "invalid_option": "Invalid option. {reason} Use: {command_hints}.",
            "invalid_command": "Invalid command. {reason} Use: {command_hints}.",
        },
        "report_flow": {
            "row_description": "Category: {category} · PDF",
            "more_section_title": "More",
            "more_reports_title": "More reports",
            "more_reports_description": "Show the next page of reports",
            "header": "Reports",
            "event_required": "This report needs an event. Select event first.",
            "choose_event": "Choose Event",
            "pick_category": "Pick a report category and tap a report.",
            "choose_report": "Choose Report",
            "pick_report": "Pick a report and tap to export",
            "report_labels": {
                "event_financial_summary": "Event Financial Summary",
                "flat_payments": "Flat Payments",
                "block_payments": "Block Payments",
                "sponsor_contributions": "Sponsor Contributions",
                "contribution_refunds": "Contribution Refunds",
                "balance_continuity": "Balance Continuity",
                "member_refunds": "Member Refunds",
                "ledger": "Ledger",
                "member_directory": "Member Directory",
                "onboarding_status": "Onboarding Status",
                "announcement_history": "Announcement History",
                "food_pass_operations": "Food Pass Operations",
                "governance_audit": "Governance Audit",
            },
        },
    },
    "hi": {
        "dashboard": {
            "sections_title": "सेक्शन",
            "main": {
                "my_account": {"title": "मेरा खाता", "description": "भागीदारी, बकाया और सहायता देखें"},
                "society": {"title": "सोसायटी", "description": "अपनी सोसायटी से जुड़ें और सदस्यता देखें"},
                "finance": {"title": "वित्त", "description": "बकाया और रिफंड ट्रैक करें"},
                "reports": {"title": "रिपोर्ट", "description": "सोसायटी रिपोर्ट देखें"},
                "administration": {"title": "प्रशासन", "description": "अनुमोदन और इवेंट संचालन संभालें"},
            },
            "my_account": {
                "participation_section": "भागीदारी",
                "finance_section": "वित्त",
                "account_section": "मेरा खाता",
                "participation": {"title": "भागीदारी", "description": "पास और इवेंट स्थिति देखें"},
                "event_status": {"title": "इवेंट स्थिति", "description": "अपनी वर्तमान इवेंट स्थिति देखें"},
                "payments": {"title": "भुगतान", "description": "बैलेंस, हिस्ट्री और रिफंड देखें"},
                "language": {"title": "भाषा", "description": "व्हाट्सऐप भाषा बदलें"},
                "help": {"title": "मदद", "description": "क्या भेजना है, इसकी जानकारी लें"},
                "menu": {"title": "मुख्य मेनू", "description": "डैशबोर्ड फिर से खोलें"},
            },
            "society": {
                "section_title": "सोसायटी",
                "join_society": {"title": "सोसायटी से जुड़ें", "description": "सदस्यता अनुरोध शुरू करें"},
                "send_join_request": {"title": "जुड़ने का अनुरोध भेजें", "description": "भेजें: join <join_code> <flat>"},
                "join_status": {"title": "जुड़ने की स्थिति", "description": "अपने अनुरोध की स्थिति देखें"},
            },
            "finance_sections": {
                "section_title": "वित्त",
                "payments": {"title": "भुगतान", "description": "बैलेंस, हिस्ट्री और रिफंड अनुरोध देखें"},
                "make_payment": {"title": "भुगतान करें", "description": "अपना बकाया चुकाएँ"},
                "request_refund": {"title": "रिफंड अनुरोध", "description": "नया रिफंड अनुरोध शुरू करें"},
                "pay_dues": {"title": "बकाया भरें", "description": "भेजें: pay <amount>"},
                "refund": {"title": "रिफंड माँगें", "description": "भेजें: refund <amount> <reason>"},
            },
        },
        "reports": {
            "intro": "एक्सपोर्ट करने के लिए रिपोर्ट चुनें। डिफ़ॉल्ट PDF है।",
            "section_title": "रिपोर्ट",
            "summary": {"title": "सारांश", "description": "इवेंट का कुल सारांश"},
            "block_report": {"title": "ब्लॉक रिपोर्ट", "description": "बिल्डिंग अनुसार विवरण"},
            "report_options": {"title": "रिपोर्ट विकल्प", "description": "एक्सपोर्ट योग्य रिपोर्ट देखें"},
            "participation_report": {"title": "भागीदारी रिपोर्ट", "description": "समिति विश्लेषण रिपोर्ट"},
        },
        "response_templates": {
            "exportable_report_options_heading": "एक्सपोर्ट योग्य रिपोर्ट विकल्प",
            "no_exportable_reports": "कोई एक्सपोर्ट योग्य रिपोर्ट कॉन्फ़िगर नहीं है।",
            "category": "श्रेणी",
            "report_key": "रिपोर्ट कुंजी",
            "label": "लेबल",
            "formats": "फ़ॉर्मैट",
            "example": "उदाहरण",
            "report_options_intro": "रिपोर्ट इवेंट और एक्सपोर्ट विकल्प चुनें।",
            "not_available": "उपलब्ध नहीं",
            "main_menu": "मुख्य मेनू",
            "help": "मदद",
            "report_options": "रिपोर्ट विकल्प",
            "invalid_option": "अमान्य विकल्प। {reason} उपयोग करें: {command_hints}.",
            "invalid_command": "अमान्य कमांड। {reason} उपयोग करें: {command_hints}.",
        },
        "report_flow": {
            "row_description": "श्रेणी: {category} · PDF",
            "more_section_title": "और",
            "more_reports_title": "और रिपोर्ट",
            "more_reports_description": "रिपोर्ट का अगला पेज दिखाएँ",
            "header": "रिपोर्ट",
            "event_required": "इस रिपोर्ट के लिए इवेंट चाहिए। पहले इवेंट चुनें।",
            "choose_event": "इवेंट चुनें",
            "pick_category": "रिपोर्ट श्रेणी चुनें और रिपोर्ट पर टैप करें।",
            "choose_report": "रिपोर्ट चुनें",
            "pick_report": "रिपोर्ट चुनें और एक्सपोर्ट करें",
            "report_labels": {
                "event_financial_summary": "इवेंट वित्तीय सारांश",
                "flat_payments": "फ्लैट भुगतान",
                "block_payments": "ब्लॉक भुगतान",
                "sponsor_contributions": "प्रायोजक योगदान",
                "contribution_refunds": "योगदान रिफंड",
                "balance_continuity": "बैलेंस निरंतरता",
                "member_refunds": "सदस्य रिफंड",
                "ledger": "लेजर",
                "member_directory": "सदस्य निर्देशिका",
                "onboarding_status": "ऑनबोर्डिंग स्थिति",
                "announcement_history": "घोषणा इतिहास",
                "food_pass_operations": "फूड पास संचालन",
                "governance_audit": "गवर्नेंस ऑडिट",
            },
        },
    },
    "gu": {
        "dashboard": {
            "sections_title": "વિભાગો",
            "main": {
                "my_account": {"title": "મારું અકાઉન્ટ", "description": "ભાગીદારી, બાકી અને સહાય જુઓ"},
                "society": {"title": "સોસાયટી", "description": "તમારી સોસાયટી જોડાઓ અને સભ્યતા જુઓ"},
                "finance": {"title": "નાણાંકીય", "description": "બાકી અને રિફંડ ટ્રેક કરો"},
                "reports": {"title": "રિપોર્ટ્સ", "description": "સોસાયટી રિપોર્ટ્સ જુઓ"},
                "administration": {"title": "પ્રશાસન", "description": "મંજૂરી અને ઇવેન્ટ કામગીરી સંભાળો"},
            },
            "my_account": {
                "participation_section": "ભાગીદારી",
                "finance_section": "નાણાંકીય",
                "account_section": "મારું અકાઉન્ટ",
                "participation": {"title": "ભાગીદારી", "description": "પાસ અને ઇવેન્ટ સ્થિતિ જુઓ"},
                "event_status": {"title": "ઇવેન્ટ સ્થિતિ", "description": "તમારી હાલની ઇવેન્ટ સ્થિતિ જુઓ"},
                "payments": {"title": "ચુકવણી", "description": "બેલેન્સ, ઇતિહાસ અને રિફંડ જુઓ"},
                "language": {"title": "ભાષા", "description": "વોટ્સએપ ભાષા બદલો"},
                "help": {"title": "મદદ", "description": "શું મોકલવું તેની માર્ગદર્શન મેળવો"},
                "menu": {"title": "મુખ્ય મેનુ", "description": "ડેશબોર્ડ ફરીથી ખોલો"},
            },
            "society": {
                "section_title": "સોસાયટી",
                "join_society": {"title": "સોસાયટી જોડાઓ", "description": "સભ્યપદ વિનંતી શરૂ કરો"},
                "send_join_request": {"title": "જોડાવાની વિનંતી મોકલો", "description": "મોકલો: join <join_code> <flat>"},
                "join_status": {"title": "જોડાવાની સ્થિતિ", "description": "તમારી વિનંતી ટ્રેક કરો"},
            },
            "finance_sections": {
                "section_title": "નાણાંકીય",
                "payments": {"title": "ચુકવણી", "description": "બેલેન્સ, ઇતિહાસ અને રિફંડ વિનંતીઓ જુઓ"},
                "make_payment": {"title": "ચુકવણી કરો", "description": "તમારું બાકી ચૂકવો"},
                "request_refund": {"title": "રિફંડ વિનંતી", "description": "નવી રિફંડ વિનંતી શરૂ કરો"},
                "pay_dues": {"title": "બાકી ભરો", "description": "મોકલો: pay <amount>"},
                "refund": {"title": "રિફંડ માંગો", "description": "મોકલો: refund <amount> <reason>"},
            },
        },
        "reports": {
            "intro": "નિકાસ કરવા માટે રિપોર્ટ પસંદ કરો. મૂળભૂત PDF છે.",
            "section_title": "રિપોર્ટ્સ",
            "summary": {"title": "સારાંશ", "description": "સમગ્ર ઇવેન્ટ સારાંશ"},
            "block_report": {"title": "બ્લોક રિપોર્ટ", "description": "બિલ્ડિંગ મુજબ વિગત"},
            "report_options": {"title": "રિપોર્ટ વિકલ્પો", "description": "નિકાસયોગ્ય રિપોર્ટ જુઓ"},
            "participation_report": {"title": "ભાગીદારી રિપોર્ટ", "description": "સમિતિ વિશ્લેષણ રિપોર્ટ"},
        },
        "response_templates": {
            "exportable_report_options_heading": "નિકાસયોગ્ય રિપોર્ટ વિકલ્પો",
            "no_exportable_reports": "કોઈ નિકાસયોગ્ય રિપોર્ટ કૉન્ફિગર નથી.",
            "category": "શ્રેણી",
            "report_key": "રિપોર્ટ કી",
            "label": "લેબલ",
            "formats": "ફોર્મેટ્સ",
            "example": "ઉદાહરણ",
            "report_options_intro": "રિપોર્ટ ઇવેન્ટ અને નિકાસ વિકલ્પ પસંદ કરો.",
            "not_available": "ઉપલબ્ધ નથી",
            "main_menu": "મુખ્ય મેનુ",
            "help": "મદદ",
            "report_options": "રિપોર્ટ વિકલ્પો",
            "invalid_option": "અમાન્ય વિકલ્પ. {reason} ઉપયોગ કરો: {command_hints}.",
            "invalid_command": "અમાન્ય કમાન્ડ. {reason} ઉપયોગ કરો: {command_hints}.",
        },
        "report_flow": {
            "row_description": "શ્રેણી: {category} · PDF",
            "more_section_title": "વધુ",
            "more_reports_title": "વધુ રિપોર્ટ્સ",
            "more_reports_description": "રિપોર્ટ્સનું આગલું પેજ બતાવો",
            "header": "રિપોર્ટ્સ",
            "event_required": "આ રિપોર્ટ માટે ઇવેન્ટ જરૂરી છે. પહેલા ઇવેન્ટ પસંદ કરો.",
            "choose_event": "ઇવેન્ટ પસંદ કરો",
            "pick_category": "રિપોર્ટ શ્રેણી પસંદ કરો અને રિપોર્ટ પર ટેપ કરો.",
            "choose_report": "રિપોર્ટ પસંદ કરો",
            "pick_report": "રિપોર્ટ પસંદ કરીને નિકાસ કરો",
            "report_labels": {
                "event_financial_summary": "ઇવેન્ટ નાણાકીય સારાંશ",
                "flat_payments": "ફ્લેટ ચુકવણીઓ",
                "block_payments": "બ્લોક ચુકવણીઓ",
                "sponsor_contributions": "પ્રાયોજક યોગદાન",
                "contribution_refunds": "યોગદાન રિફંડ",
                "balance_continuity": "બેલેન્સ સતતતા",
                "member_refunds": "સભ્ય રિફંડ",
                "ledger": "લેજર",
                "member_directory": "સભ્ય ડિરેક્ટરી",
                "onboarding_status": "ઓનબોર્ડિંગ સ્થિતિ",
                "announcement_history": "જાહેરાત ઇતિહાસ",
                "food_pass_operations": "ફૂડ પાસ ઓપરેશન્સ",
                "governance_audit": "ગવર્નન્સ ઓડિટ",
            },
        },
    },
}


def get_catalog(lang: str | None = None) -> CatalogDict:
    normalized_language = normalize_language_code(lang) or DEFAULT_LANGUAGE
    return TRANSLATIONS.get(normalized_language, TRANSLATIONS[DEFAULT_LANGUAGE])


def _resolve_key_path(catalog: Mapping[str, CatalogValue], key: str) -> CatalogValue | None:
    current: CatalogValue | None = catalog
    for part in key.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def translate(key: str, lang: str | None = None, **params: Any) -> str:
    normalized_language = normalize_language_code(lang) or DEFAULT_LANGUAGE
    value = _resolve_key_path(TRANSLATIONS.get(normalized_language, {}), key)
    if value is None and normalized_language != DEFAULT_LANGUAGE:
        value = _resolve_key_path(TRANSLATIONS[DEFAULT_LANGUAGE], key)
    if value is None:
        raise KeyError(f"Missing translation for key: {key}")
    if not isinstance(value, str):
        raise KeyError(f"Translation key does not resolve to a string: {key}")
    return value.format(**params) if params else value
