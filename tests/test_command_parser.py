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
    assert "Category must be one of" in error


def test_parse_report_export_invalid_format():
    error = parse_report_export(
        "report export --category financial --report event-summary --format json"
    )
    assert isinstance(error, str)
    assert "Format must be one of" in error


def test_parse_report_export_invalid_filter_token():
    error = parse_report_export(
        "report export --category financial --report event-summary --format pdf event_id=evt-1"
    )
    assert isinstance(error, str)
    assert "Unsupported token" in error
