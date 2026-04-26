from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts import bootstrap_seed, map_user_to_flat, reset_event, seed_flats, seed_periodic_tasks
from tests.utils import QueryMock


class _QuerySequenceDB:
    def __init__(self, queries):
        self._queries = list(queries)
        for query in self._queries:
            if not hasattr(query, "delete"):
                query.delete = MagicMock(return_value=None)
        self._index = 0
        self.commit = MagicMock()
        self.add = MagicMock()

    def query(self, *_args, **_kwargs):
        query = self._queries[self._index]
        self._index += 1
        return query


def test_map_user_to_flat_raises_when_society_missing():
    db = _QuerySequenceDB([QueryMock(first_result=None)])

    with pytest.raises(ValueError, match="No society found"):
        map_user_to_flat.map_user_to_flat(db, user_identifier="user-1", flat_number="E-303")


def test_map_user_to_flat_assigns_user(monkeypatch):
    society = SimpleNamespace(id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    db = _QuerySequenceDB([QueryMock(first_result=society), QueryMock(first_result=flat)])

    assign_mock = MagicMock()
    monkeypatch.setattr(map_user_to_flat.UserFlatService, "assign_user_to_flat", assign_mock)

    map_user_to_flat.map_user_to_flat(db, user_identifier="user-1", flat_number="E-303")

    assign_mock.assert_called_once_with(
        db=db,
        society_id="soc-1",
        flat_id="flat-1",
        user_identifier="user-1",
    )


def test_reset_latest_event_raises_when_workflow_missing():
    event = SimpleNamespace(id="event-1", status="ACTIVE")
    db = _QuerySequenceDB(
        [
            QueryMock(first_result=event),
            QueryMock(),
            QueryMock(),
            QueryMock(),
            QueryMock(),
            QueryMock(first_result=None),
        ]
    )

    with pytest.raises(ValueError, match="No workflow state found"):
        reset_event.reset_latest_event(db)


def test_reset_latest_event_updates_status_and_commits():
    event = SimpleNamespace(id="event-1", status="ACTIVE")
    workflow = SimpleNamespace(current_state="ACTIVE", allowed_next_states=[])
    db = _QuerySequenceDB(
        [
            QueryMock(first_result=event),
            QueryMock(),
            QueryMock(),
            QueryMock(),
            QueryMock(),
            QueryMock(first_result=workflow),
        ]
    )

    reset_event.reset_latest_event(db)

    assert workflow.current_state == "DRAFT"
    assert workflow.allowed_next_states == ["ACTIVE"]
    assert event.status == "DRAFT"
    db.commit.assert_called_once()


def test_seed_flats_raises_when_society_missing():
    db = _QuerySequenceDB([QueryMock(first_result=None)])

    with pytest.raises(ValueError, match="No society found"):
        seed_flats.seed_flats(db)


def test_seed_flats_is_idempotent_when_flat_exists():
    society = SimpleNamespace(id="soc-1")
    existing_flat = SimpleNamespace(id="flat-1")
    db = _QuerySequenceDB([QueryMock(first_result=society), QueryMock(first_result=existing_flat)])

    created = seed_flats.seed_flats(db, flats=(("A-804", "A", "JK"),))

    assert created == 0
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_seed_flats_adds_missing_flat():
    society = SimpleNamespace(id="soc-1")
    db = _QuerySequenceDB([QueryMock(first_result=society), QueryMock(first_result=None)])

    created = seed_flats.seed_flats(db, flats=(("A-804", "A", "JK"),))

    assert created == 1
    db.add.assert_called_once()
    db.commit.assert_not_called()


def test_seed_periodic_tasks_raises_when_society_missing():
    db = _QuerySequenceDB([QueryMock(first_result=None)])

    with pytest.raises(ValueError, match="No society found"):
        seed_periodic_tasks.seed_periodic_tasks(db)


def test_seed_periodic_tasks_is_idempotent_when_existing():
    society = SimpleNamespace(id="soc-1")
    existing = SimpleNamespace(id="cfg-1")
    # 1 for society, 4 for existing tasks
    db = _QuerySequenceDB([
        QueryMock(first_result=society),
        QueryMock(first_result=existing),
        QueryMock(first_result=existing),
        QueryMock(first_result=existing),
        QueryMock(first_result=existing),
    ])

    created = seed_periodic_tasks.seed_periodic_tasks(db)

    assert created is False
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_seed_periodic_tasks_creates_when_missing():
    society = SimpleNamespace(id="soc-1")
    # 1 for society, 4 for missing tasks
    db = _QuerySequenceDB([
        QueryMock(first_result=society),
        QueryMock(first_result=None),
        QueryMock(first_result=None),
        QueryMock(first_result=None),
        QueryMock(first_result=None),
    ])

    created = seed_periodic_tasks.seed_periodic_tasks(db)

    assert created is True
    assert db.add.call_count == 4
    db.commit.assert_not_called()


def test_bootstrap_validated_overrides_parses_required_fields():
    overrides = bootstrap_seed._validated_bootstrap_overrides(  # noqa: SLF001
        {
            "society": {
                "name": "Alpha Society",
                "city": "Austin",
                "state": "Texas",
                "timezone": "America/Chicago",
            },
            "onboarding": {"join_code": "JOIN-007", "approval_required": False},
            "chairman": {
                "name": "Jane Doe",
                "phone": "+15125550123",
                "channel_identity": {"channel_type": "whatsapp", "external_user_id": "15125550123"},
            },
            "flats": [{"flat_number": "A-101", "block": "A", "owner_name": "Owner 1"}],
            "reminder_defaults": {"enabled": True, "run_hour": 9, "run_minute": 30, "frequency": "daily"},
        }
    )

    assert overrides["society_name"] == "Alpha Society"
    assert overrides["flats"] == (("A-101", "A", "Owner 1"),)
    assert overrides["reminder_run_hour"] == 9


def test_bootstrap_validated_overrides_fails_fast_for_bad_config():
    with pytest.raises(ValueError, match="Invalid bootstrap config: missing required field 'chairman.phone'"):
        bootstrap_seed._validated_bootstrap_overrides(  # noqa: SLF001
            {
                "society": {
                    "name": "Alpha Society",
                    "city": "Austin",
                    "state": "Texas",
                    "timezone": "America/Chicago",
                },
                "onboarding": {"join_code": "JOIN-007"},
                "chairman": {
                    "name": "Jane Doe",
                    "channel_identity": {"external_user_id": "15125550123"},
                },
                "flats": [{"flat_number": "A-101", "block": "A", "owner_name": "Owner 1"}],
                "reminder_defaults": {"run_hour": 9, "run_minute": 30, "frequency": "daily"},
            }
        )
