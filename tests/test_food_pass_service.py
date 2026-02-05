from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import EventFoodPass, Payment
from app.modules.events.food_pass_service import FoodPassService
from tests.utils import QueryMock


def test_add_or_update_pass_creates_food_pass_and_payment(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=None),
        QueryMock(first_result=None)
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    food_pass = FoodPassService.add_or_update_pass(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        veg_count=2,
        jain_count=1,
        kids_count=0,
        charge_per_person=300,
        performed_by="member-1"
    )

    assert food_pass.total_amount == 900
    assert food_pass.is_participating is True
    db.commit.assert_called_once()

    added_types = [type(call.args[0]) for call in db.add.call_args_list]
    assert EventFoodPass in added_types
    assert Payment in added_types


def test_add_or_update_pass_requires_nonzero_counts(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat)
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    with pytest.raises(Exception, match="At least one food count"):
        FoodPassService.add_or_update_pass(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            veg_count=0,
            jain_count=0,
            kids_count=0,
            charge_per_person=300,
            performed_by="member-1"
        )


def test_mark_not_participating_updates_existing_pass(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    food_pass = SimpleNamespace(
        veg_count=1,
        jain_count=1,
        kids_count=0,
        total_amount=600,
        is_participating=True
    )
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=food_pass)
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    updated = FoodPassService.mark_not_participating(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        performed_by="member-1"
    )

    assert updated.total_amount == 0
    assert updated.is_participating is False
    db.commit.assert_called_once()
