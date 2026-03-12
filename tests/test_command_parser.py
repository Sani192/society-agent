from app.commands.parser import parse_event_creation, parse_pass_counts


def test_parse_event_creation_valid_payload():
    parsed, error = parse_event_creation(
        "add event Holi | 2026-03-10 19:00 | food: veg,jain | adult:300 | child:150 | deadline:2026-03-09 18:00"
    )

    assert error is None
    assert parsed["name"] == "Holi"
    assert parsed["food_types"] == ["veg", "jain"]
    assert parsed["charge_per_adult"] == 300


def test_parse_event_creation_invalid_missing_fields():
    parsed, error = parse_event_creation("add event Holi | 2026-03-10 19:00 | food: veg")

    assert parsed is None
    assert "Missing fields." in error


def test_parse_pass_counts_accepts_kids_token():
    counts = parse_pass_counts("add pass veg 2 jain 1 kids 1")

    assert counts == {"veg": 2, "jain": 1, "kids": 1}


def test_parse_pass_counts_accepts_kid_alias():
    counts = parse_pass_counts("add pass veg 2 jain 1 kid 1")

    assert counts == {"veg": 2, "jain": 1, "kids": 1}
