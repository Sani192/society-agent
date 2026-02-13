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
