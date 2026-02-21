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


def test_detect_intent_conversational_export_selection():
    assert detect_intent("export 2") == "EXPORT_SELECTION"


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


def test_detect_intent_event_selection_command():
    assert detect_intent("event 2") == "EXPORT_SELECTION"


def test_detect_intent_activate_event_command():
    assert detect_intent("activate event") == "ACTIVATE_EVENT"


def test_detect_intent_lock_passes_command():
    assert detect_intent("lock passes") == "LOCK_PASSES"


def test_detect_intent_start_event_command():
    assert detect_intent("start event") == "START_EVENT"
