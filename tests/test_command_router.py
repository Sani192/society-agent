from app.commands.router import detect_intent


def test_detect_intent_report_export_modern():
    assert (
        detect_intent(
            "report export --category financial --report event-summary --format pdf"
        )
        == "EXPORT_REPORT"
    )


def test_detect_intent_legacy_export_not_supported():
    assert detect_intent("export financial event-summary pdf") is None


def test_detect_intent_report_options():
    assert detect_intent("report options") == "REPORT_OPTIONS"


def test_detect_intent_reports_alias():
    assert detect_intent("reports") == "REPORTS"


def test_detect_intent_conversational_export_selection():
    assert detect_intent("export 2") == "EXPORT_SELECTION"


def test_detect_intent_conversational_choose_report():
    assert detect_intent("choose report event-summary") == "CHOOSE_REPORT"


def test_detect_intent_export_prefix_without_number_still_not_supported():
    assert detect_intent("export financial event-summary pdf") is None
