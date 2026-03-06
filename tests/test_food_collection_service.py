from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import EventFoodCounter, EventFoodToken
from app.modules.events.food_collection_service import FoodCollectionService, TOKEN_ALPHABET
from tests.utils import QueryMock


def test_generate_tokens_for_event_creates_one_token_per_plate(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    passes = [SimpleNamespace(flat_id="flat-1", veg_count=2, jain_count=1, kids_count=1)]

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(scalar_result=0),
        QueryMock(all_result=passes),
    ]

    tokens = FoodCollectionService.generate_tokens_for_event(
        db=db,
        event_id="event-1",
        performed_by="member-1",
    )

    assert len(tokens) == 4
    assert all(len(row.token_code) == 6 for row in tokens)
    assert all(ch in TOKEN_ALPHABET for row in tokens for ch in row.token_code)
    assert {row.food_type for row in tokens} == {"veg", "jain", "kids"}
    db.commit.assert_called_once()


def test_generate_tokens_for_event_rejects_regeneration():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(scalar_result=2),
    ]

    with pytest.raises(Exception, match="already generated"):
        FoodCollectionService.generate_tokens_for_event(
            db=db,
            event_id="event-1",
            performed_by="member-1",
        )


def test_open_food_counter_marks_counter_open():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=None),
    ]

    counter = FoodCollectionService.open_food_counter(
        db=db,
        event_id="event-1",
        performed_by="member-1",
        auto_close_minutes=90,
    )

    assert isinstance(counter, EventFoodCounter)
    assert counter.is_open is True
    assert counter.closes_at - counter.opened_at == timedelta(minutes=90)
    db.commit.assert_called_once()


def test_verify_and_serve_token_rejects_used_token():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    counter = SimpleNamespace(is_open=True, closes_at=None)
    token = SimpleNamespace(id="t-1", served_at="done", served_method="QR_SCAN")

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=counter),
        QueryMock(first_result=token),
    ]

    with pytest.raises(Exception, match="already used"):
        FoodCollectionService.verify_and_serve_token(
            db=db,
            event_id="event-1",
            token_code="ABCD23",
            method="manual_token",
            performed_by="member-1",
        )


def test_member_pass_status_builds_totals_and_remaining():
    rows = [
        SimpleNamespace(token_code="A", food_type="veg", served_at=None),
        SimpleNamespace(token_code="B", food_type="veg", served_at="done"),
        SimpleNamespace(token_code="C", food_type="kids", served_at=None),
    ]
    db = MagicMock()
    db.query.side_effect = [QueryMock(all_result=rows)]

    summary = FoodCollectionService.member_pass_status(db=db, event_id="event-1", flat_id="flat-1")

    assert summary["total_passes"] == 3
    assert summary["served"] == 1
    assert summary["remaining"] == 2
    assert summary["by_type"]["veg"]["remaining"] == 1
    assert summary["by_type"]["kids"]["remaining"] == 1


def test_dashboard_returns_recent_served_in_descending_order():
    rows = [
        SimpleNamespace(token_code="A", flat_id="f1", food_type="veg", served_at=None),
        SimpleNamespace(token_code="B", flat_id="f1", food_type="veg", served_at=2),
        SimpleNamespace(token_code="C", flat_id="f2", food_type="kids", served_at=3),
    ]
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(all_result=rows),
        QueryMock(all_result=[SimpleNamespace(id="f2", flat_number="A-102")]),
    ]

    dashboard = FoodCollectionService.dashboard(db=db, event_id="event-1", recent_limit=1)

    assert dashboard["total_plates"] == 3
    assert dashboard["served_plates"] == 2
    assert dashboard["remaining_plates"] == 1
    assert dashboard["recent_served"][0]["token"] == "C"
    assert dashboard["recent_served"][0]["flat_number"] == "A-102"


def test_serve_by_flat_lookup_picks_first_unserved(monkeypatch):
    token = SimpleNamespace(token_code="QW23RT")
    db = MagicMock()
    db.query.side_effect = [QueryMock(first_result=token)]

    verify = MagicMock(return_value="served")
    monkeypatch.setattr(FoodCollectionService, "verify_and_serve_token", verify)

    result = FoodCollectionService.serve_by_flat_lookup(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        performed_by="member-1",
    )

    assert result == "served"
    verify.assert_called_once_with(
        db=db,
        event_id="event-1",
        token_code="QW23RT",
        method="FLAT_LOOKUP",
        performed_by="member-1",
    )


def test_serve_by_flat_lookup_rejects_if_no_token():
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=None),
        QueryMock(first_result=None),
    ]

    with pytest.raises(Exception, match="Invalid event"):
        FoodCollectionService.serve_by_flat_lookup(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            performed_by="member-1",
        )


def test_serve_by_flat_lookup_allows_fallback_without_tokens():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    counter = SimpleNamespace(is_open=True, closes_at=None)
    food_pass = SimpleNamespace(veg_count=1, jain_count=0, kids_count=0)

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=None),
        QueryMock(first_result=event),
        QueryMock(first_result=counter),
        QueryMock(first_result=food_pass),
        QueryMock(scalar_result=0),
        QueryMock(scalar_result=0),
    ]

    served = FoodCollectionService.serve_by_flat_lookup(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        performed_by="member-1",
    )

    assert served.token_code == "FALLBACK"
    db.commit.assert_called_once()


def test_serve_by_flat_lookup_fallback_rejects_when_entitlement_consumed():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    counter = SimpleNamespace(is_open=True, closes_at=None)
    food_pass = SimpleNamespace(veg_count=1, jain_count=0, kids_count=0)

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=None),
        QueryMock(first_result=event),
        QueryMock(first_result=counter),
        QueryMock(first_result=food_pass),
        QueryMock(scalar_result=1),
        QueryMock(scalar_result=0),
    ]

    with pytest.raises(Exception, match="No remaining tokens"):
        FoodCollectionService.serve_by_flat_lookup(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            performed_by="member-1",
        )


def test_committee_flat_status_scopes_flat_by_event_society():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", flat_number="A-101")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(all_result=[]),
    ]

    summary = FoodCollectionService.committee_flat_status(
        db=db,
        event_id="event-1",
        flat_number="A-101",
    )

    assert summary["flat_number"] == "A-101"
