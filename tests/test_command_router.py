from app.channels.whatsapp.response_templates import EXPORT_COMMAND_EXAMPLES
from app.commands.router import detect_intent


def test_detect_intent_legacy_export_not_supported():
    assert detect_intent("export financial event-summary pdf") is None


def test_detect_intent_report_options():
    assert detect_intent("report options") == "REPORT_OPTIONS"



def test_detect_intent_conversational_export_selection_when_allowed():
    assert detect_intent("export 2", allow_numeric_export_selection=True) == "EXPORT_SELECTION"


def test_detect_intent_conversational_export_selection_when_not_allowed():
    assert detect_intent("export 2", allow_numeric_export_selection=False) is None


def test_detect_intent_numeric_only_export_selection_when_allowed():
    assert detect_intent("2", allow_numeric_export_selection=True) == "EXPORT_SELECTION"


def test_detect_intent_numeric_only_export_selection_when_not_allowed():
    assert detect_intent("2", allow_numeric_export_selection=False) is None


def test_detect_intent_interactive_export_selection():
    assert detect_intent("export::financial:ledger") == "EXPORT_SELECTION"


def test_detect_intent_export_prefix_without_number_still_not_supported():
    assert detect_intent("export financial event-summary pdf") is None


def test_detect_intent_format_command_not_supported():
    assert detect_intent("format pdf") is None


def test_detect_intent_event_selection_command_when_allowed():
    assert detect_intent("event 2", allow_numeric_export_selection=True) == "EXPORT_SELECTION"


def test_detect_intent_event_selection_command_when_not_allowed():
    assert detect_intent("event 2", allow_numeric_export_selection=False) is None


def test_detect_intent_activate_event_command():
    assert detect_intent("activate event") == "ACTIVATE_EVENT"


def test_detect_intent_lock_passes_command():
    assert detect_intent("lock passes") == "LOCK_PASSES"


def test_detect_intent_start_event_command():
    assert detect_intent("start event") == "START_EVENT"


def test_detect_intent_food_collection_commands():
    assert detect_intent("generate food tokens") == "GENERATE_FOOD_TOKENS"
    assert detect_intent("open food counter") == "OPEN_FOOD_COUNTER"
    assert detect_intent("verify food token AB12CD") == "VERIFY_FOOD_TOKEN"
    assert detect_intent("scan food qr ZX34KM") == "SCAN_FOOD_QR"
    assert detect_intent("serve flat A-101") == "SERVE_FOOD_FLAT"
    assert detect_intent("flat passes A-101") == "FLAT_PASS_STATUS"
    assert detect_intent("token status AB12CD") == "TOKEN_STATUS"
    assert detect_intent("food dashboard") == "FOOD_DASHBOARD"


def test_detect_intent_pay_sentence_like_text_not_mapped():
    assert detect_intent("can you help me pay this invoice?") is None


def test_detect_intent_refund_sentence_like_text_not_mapped():
    assert detect_intent("i need a refund for this ticket") is None


def test_detect_intent_summary_sentence_like_text_not_mapped():
    assert detect_intent("can you share a summary of yesterday") is None


def test_detect_intent_help_sentence_like_text_not_mapped():
    assert detect_intent("please help me with this") is None


def test_detect_intent_high_risk_generic_intents_keep_controlled_prefixes():
    assert detect_intent("pay 500") == "PAY"
    assert detect_intent("refund 200 reason guest absent") == "REFUND"
    assert detect_intent("summary now") == "SUMMARY"
    assert detect_intent("help menu") == "HELP"


def test_detect_intent_committee_member_crud_commands():
    assert detect_intent("committee members") == "LIST_COMMITTEE_MEMBERS"
    assert detect_intent("add committee member Alice|+91 9999900000|secretary") == "ADD_COMMITTEE_MEMBER"
    assert detect_intent("remove committee member 123") == "REMOVE_COMMITTEE_MEMBER"
    assert detect_intent("change committee role 123 treasurer") == "CHANGE_COMMITTEE_ROLE"


def test_export_command_examples_are_detectable():
    for example in EXPORT_COMMAND_EXAMPLES:
        assert detect_intent(example) in {"REPORT_OPTIONS", "EXPORT_SELECTION"}


def test_detect_intent_localized_hindi_commands_map_to_same_intents():
    assert detect_intent("रिपोर्ट विकल्प", language="hi") == "REPORT_OPTIONS"
    assert detect_intent("सारांश अब", language="hi") == "SUMMARY"
    assert detect_intent("भुगतान 500", language="hi") == "PAY"
    assert detect_intent("वापसी 200", language="hi") == "REFUND"
    assert detect_intent("मदद मेनू", language="hi") == "HELP"


def test_detect_intent_localized_gujarati_commands_map_to_same_intents():
    assert detect_intent("રિપોર્ટ વિકલ્પો", language="gu") == "REPORT_OPTIONS"
    assert detect_intent("સારાંશ હવે", language="gu") == "SUMMARY"
    assert detect_intent("ચુકવણી 700", language="gu") == "PAY"
    assert detect_intent("પરત 100", language="gu") == "REFUND"
    assert detect_intent("મદદ મેનુ", language="gu") == "HELP"


def test_detect_intent_localized_high_risk_gating_blocks_sentence_starters():
    assert detect_intent("भुगतान कृपया इसको करें", language="hi") is None
    assert detect_intent("ચુકવો કૃપા કરીને આ ઇન્વોઇસ", language="gu") is None
