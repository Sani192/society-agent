from app.channels.whatsapp.report_flow import _build_reports_list_sections
from app.i18n.catalog import get_catalog, translate
from app.whatsapp.response_templates import build_invalid_command_response, format_report_options_response
from app.whatsapp.ui.dashboard import (
    build_finance_sections,
    build_main_dashboard_sections,
    build_my_account_sections,
    build_society_sections,
)
from app.whatsapp.ui.reports import build_reports_sections, reports_intro


def test_translate_falls_back_to_english_for_unknown_language_code():
    assert translate("dashboard.sections_title", "mr") == "Sections"


def test_translate_falls_back_to_english_when_key_missing_in_selected_language():
    original_hi = get_catalog("hi")["dashboard"]["sections_title"]
    del get_catalog("hi")["dashboard"]["sections_title"]
    try:
        assert translate("dashboard.sections_title", "hi") == "Sections"
    finally:
        get_catalog("hi")["dashboard"]["sections_title"] = original_hi


def test_dashboard_sections_are_localized_in_hindi():
    main_sections = build_main_dashboard_sections(is_committee=True, lang="hi")
    my_account_sections = build_my_account_sections(lang="hi")
    society_sections = build_society_sections(lang="hi")
    finance_sections = build_finance_sections(include_payment_actions=True, lang="hi")

    assert main_sections[0]["title"] == "सेक्शन"
    assert main_sections[0]["rows"][0]["title"] == "मेरा खाता"
    assert my_account_sections[2]["rows"][0]["title"] == "भाषा"
    assert society_sections[0]["rows"][0]["title"] == "सोसायटी से जुड़ें"
    assert finance_sections[0]["rows"][0]["title"] == "भुगतान करें"


def test_reports_ui_and_templates_are_localized_in_gujarati():
    sections = build_reports_sections(is_committee=True, lang="gu")
    intro = reports_intro(lang="gu")
    formatted = format_report_options_response(
        [
            {
                "category": "financial",
                "report_key": "ledger",
                "label": "Ledger",
                "supported_formats": ["pdf"],
                "example_command": "export::financial:ledger",
            }
        ],
        lang="gu",
    )

    assert sections[0]["title"] == "રિપોર્ટ્સ"
    assert sections[0]["rows"][2]["title"] == "રિપોર્ટ વિકલ્પો"
    assert intro == "નિકાસ કરવા માટે રિપોર્ટ પસંદ કરો. મૂળભૂત PDF છે."
    assert "*શ્રેણી*: financial" in formatted


def test_invalid_command_response_uses_localized_default_ctas():
    text, contract = build_invalid_command_response(
        channel="whatsapp",
        reason="कृपया सूची से चुनें।",
        lang="hi",
    )

    assert "अमान्य विकल्प" in text
    assert contract.ctas == (
        {"id": "menu", "label": "मुख्य मेनू"},
        {"id": "help", "label": "मदद"},
    )


def test_report_flow_sections_use_localized_more_row_and_fallback_to_english():
    sections = _build_reports_list_sections(
        [
            {"category": "financial", "command_key": "financial:ledger", "label": "Ledger"},
            {"category": "financial", "command_key": "financial:summary", "label": "Summary"},
        ],
        page_size=1,
        include_more_row=True,
        lang="gu",
    )
    fallback_sections = _build_reports_list_sections(
        [{"category": "financial", "command_key": "financial:ledger", "label": "Ledger"}],
        lang="xx",
    )

    assert sections[-1]["title"] == "વધુ"
    assert sections[-1]["rows"][0]["title"] == "વધુ રિપોર્ટ્સ"
    assert sections[0]["rows"][0]["description"] == "શ્રેણી: Financial · PDF"
    assert fallback_sections[0]["rows"][0]["description"] == "Category: Financial · PDF"
