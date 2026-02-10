from app.commands.parser import parse_report_export


def test_parse_report_export_valid_basic():
    parsed = parse_report_export("export financial event-summary pdf")
    assert isinstance(parsed, dict)
    assert parsed == {
        "category": "financial",
        "report": "event-summary",
        "format": "pdf",
        "filters": {},
        "event_id": None,
    }


def test_parse_report_export_valid_with_event_id_equals():
    parsed = parse_report_export("export financial event-summary csv event_id=evt-1")
    assert isinstance(parsed, dict)
    assert parsed["format"] == "csv"
    assert parsed["event_id"] == "evt-1"
    assert parsed["filters"] == {"event_id": "evt-1"}


def test_parse_report_export_valid_with_event_id_pair():
    parsed = parse_report_export("export financial event-summary excel event_id evt-2")
    assert isinstance(parsed, dict)
    assert parsed["event_id"] == "evt-2"


def test_parse_report_export_invalid_missing_parts():
    error = parse_report_export("export financial")
    assert isinstance(error, str)
    assert "Use: export financial event-summary pdf" in error


def test_parse_report_export_invalid_category():
    error = parse_report_export("export personal event-summary pdf")
    assert isinstance(error, str)
    assert "Category must be one of" in error


def test_parse_report_export_invalid_format():
    error = parse_report_export("export financial event-summary json")
    assert isinstance(error, str)
    assert "Format must be one of" in error


def test_parse_report_export_invalid_filter_token():
    error = parse_report_export("export financial event-summary pdf foo=bar")
    assert isinstance(error, str)
    assert "Unsupported filter token" in error
