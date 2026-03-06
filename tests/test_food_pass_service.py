from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import EventFoodPass, Payment
from app.modules.events.food_pass_service import FoodPassService
from tests.utils import QueryMock


def test_add_or_update_pass_creates_food_pass_and_payment(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-1")
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
        charge_per_adult=300,
        charge_per_child=150,
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
    flat = SimpleNamespace(id="flat-1", society_id="soc-1")
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
            charge_per_adult=300,
            charge_per_child=150,
            performed_by="member-1"
        )




def test_add_or_update_pass_rejects_flat_from_different_society(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-2")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat)
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    with pytest.raises(Exception, match="Flat does not belong to the event society"):
        FoodPassService.add_or_update_pass(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            veg_count=1,
            jain_count=0,
            kids_count=0,
            charge_per_adult=300,
            charge_per_child=150,
            performed_by="member-1"
        )


def test_mark_not_participating_rejects_flat_from_different_society(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-2")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat)
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    with pytest.raises(Exception, match="Flat does not belong to the event society"):
        FoodPassService.mark_not_participating(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            performed_by="member-1"
        )

def test_mark_not_participating_updates_existing_pass(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-1")
    food_pass = SimpleNamespace(
        veg_count=1,
        jain_count=1,
        kids_count=0,
        total_amount=600,
        is_participating=True
    )
    db = MagicMock()
    payment = SimpleNamespace(expected_amount=600, paid_amount=200, status="partial")
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=food_pass),
        QueryMock(first_result=payment)
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
    assert payment.expected_amount == 0
    assert payment.status == "refunded"
    db.commit.assert_called_once()


def test_mark_not_participating_creates_payment_when_missing(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-1")
    food_pass = SimpleNamespace(
        veg_count=1,
        jain_count=0,
        kids_count=1,
        total_amount=450,
        is_participating=True
    )
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=food_pass),
        QueryMock(first_result=None)
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    FoodPassService.mark_not_participating(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        performed_by="member-1"
    )

    created_payment = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Payment)
    )
    assert created_payment.expected_amount == 0
    assert created_payment.paid_amount == 0
    assert created_payment.status == "pending"


@pytest.mark.parametrize("state", ["DRAFT", "LOCKED"])
def test_add_or_update_pass_denies_non_committee_override_attempt(state, monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(
            allowed=False,
            requires_override=False,
            message=(
                f"Override denied: only chairman, secretary, or treasurer may override in state {state}"
            ),
        ),
    )

    apply_override = MagicMock()
    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.apply_override",
        apply_override,
    )

    with pytest.raises(Exception, match="only chairman, secretary, or treasurer"):
        FoodPassService.add_or_update_pass(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            veg_count=1,
            jain_count=0,
            kids_count=0,
            charge_per_adult=300,
            charge_per_child=150,
            performed_by="resident-member",
            override_reason="Need override",
        )

    apply_override.assert_not_called()


def test_add_or_update_pass_requires_performer_before_override(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1", society_id="soc-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
    ]

    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(
            allowed=False,
            requires_override=True,
            message="Action requires override",
        ),
    )

    apply_override = MagicMock()
    monkeypatch.setattr(
        "app.modules.events.food_pass_service.WorkflowEngine.apply_override",
        apply_override,
    )

    with pytest.raises(Exception, match="Override denied: performer required"):
        FoodPassService.add_or_update_pass(
            db=db,
            event_id="event-1",
            flat_id="flat-1",
            veg_count=1,
            jain_count=0,
            kids_count=0,
            charge_per_adult=300,
            charge_per_child=150,
            performed_by=None,
            override_reason="Committee override",
        )

    apply_override.assert_not_called()
