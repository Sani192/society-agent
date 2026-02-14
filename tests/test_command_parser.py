from app.commands.parser import parse_report_export


def test_parse_report_export_valid_modern_named_flags():
    parsed = parse_report_export(
        "report export --category financial --report event-summary --format pdf"
    )
    assert isinstance(parsed, dict)
    assert parsed == {
        "category": "financial",
        "report": "event-summary",
        "format": "pdf",
        "filters": {},
        "event_id": None,
    }


def test_parse_report_export_valid_with_event_id_flag():
    parsed = parse_report_export(
        "report export --category financial --report event-summary --format excel --event-id evt-2"
    )
    assert isinstance(parsed, dict)
    assert parsed["event_id"] == "evt-2"


def test_parse_report_export_invalid_legacy_syntax():
    error = parse_report_export("export financial event-summary pdf")
    assert isinstance(error, str)
    assert (
        "Use: report export --category financial --report event-summary --format pdf"
        in error
    )


def test_parse_report_export_invalid_missing_parts():
    error = parse_report_export("report export --category financial")
    assert isinstance(error, str)
    assert (
        "Use: report export --category financial --report event-summary --format pdf"
        in error
    )


def test_parse_report_export_invalid_category():
    error = parse_report_export(
        "report export --category personal --report event-summary --format pdf"
    )
    assert isinstance(error, str)
    assert "Invalid category: personal" in error
    assert "Accepted values: admin, financial, governance" in error
    assert "Example: report export --category financial --report event-summary --format pdf" in error


def test_parse_report_export_invalid_format():
    error = parse_report_export(
        "report export --category financial --report event-summary --format json"
    )
    assert isinstance(error, str)
    assert "Invalid format: json" in error
    assert "Accepted values: csv, excel, pdf" in error
    assert "Example: report export --category financial --report event-summary --format pdf" in error


def test_parse_report_export_invalid_filter_token():
    error = parse_report_export(
        "report export --category financial --report event-summary --format pdf event_id=evt-1"
    )
    assert isinstance(error, str)
    assert "Unsupported token" in error


def test_parse_report_export_invalid_report_for_category():
    error = parse_report_export(
        "report export --category admin --report event-summary --format pdf"
    )
    assert isinstance(error, str)
    assert "Invalid report: event-summary for category admin" in error
    assert "Accepted values: member-directory, onboarding-status" in error
    assert "Try: report options" in error
    assert "Example: report export --category financial --report event-summary --format pdf" in error
