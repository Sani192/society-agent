from app.commands.router import detect_intent


def test_detect_intent_report_export_modern_not_supported():
    assert (
        detect_intent(
            "report export --category financial --report event-summary --format pdf"
        )
        is None
    )


def test_detect_intent_legacy_export_not_supported():
    assert detect_intent("export financial event-summary pdf") is None


def test_detect_intent_report_options():
    assert detect_intent("report options") == "REPORT_OPTIONS"


def test_detect_intent_reports_alias_not_supported():
    assert detect_intent("reports") is None


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
