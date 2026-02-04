from types import SimpleNamespace

from app.db.models import AuditLog, SocietyBalance
from app.modules.ledger.ledger_service import LedgerService
from tests.utils import QueryMock


def test_calculate_event_balance_updates_existing_balance(db_session):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    existing_balance = SimpleNamespace(opening_balance=0, closing_balance=0)

    db_session.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(scalar_result=500),
        QueryMock(scalar_result=200),
        QueryMock(scalar_result=150),
        QueryMock(scalar_result=50),
        QueryMock(first_result=existing_balance),
    ]

    result = LedgerService.calculate_event_balance(
        db_session,
        event_id=event.id,
        opening_balance=100,
        performed_by="member-1"
    )

    assert result is existing_balance
    assert existing_balance.opening_balance == 100
    assert existing_balance.closing_balance == 600
    assert any(
        isinstance(call.args[0], AuditLog)
        for call in db_session.add.call_args_list
    )
    db_session.commit.assert_called_once()


def test_calculate_event_balance_creates_new_balance(db_session):
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    db_session.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(scalar_result=300),
        QueryMock(scalar_result=0),
        QueryMock(scalar_result=80),
        QueryMock(scalar_result=20),
        QueryMock(first_result=None),
    ]

    result = LedgerService.calculate_event_balance(
        db_session,
        event_id=event.id,
        opening_balance=50,
        performed_by="member-2",
        override_reason="manual check"
    )

    assert isinstance(result, SocietyBalance)
    assert result.opening_balance == 50
    assert result.closing_balance == 250
    added_types = [type(call.args[0]) for call in db_session.add.call_args_list]
    assert SocietyBalance in added_types
    assert AuditLog in added_types
    db_session.commit.assert_called_once()
