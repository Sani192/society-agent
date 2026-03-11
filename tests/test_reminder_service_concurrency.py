from datetime import date
from types import SimpleNamespace

from app.modules.reminders.reminder_service import ReminderService


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def first(self):
        return self._result

    def all(self):
        return self._result


class _SharedReminderStore:
    def __init__(self):
        self.keys = set()


class _FakeSession:
    def __init__(self, shared_store):
        self._shared_store = shared_store
        self._query_stage = 0
        self.exists_checks = 0
        self.commits = 0

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def query(self, _model):
        self._query_stage += 1
        if self._query_stage == 1:
            return _FakeQuery(SimpleNamespace(id="event-1", society_id="soc-1"))
        if self._query_stage == 2:
            return _FakeQuery([SimpleNamespace(flat_id="flat-1", expected_amount=500, paid_amount=200)])
        if self._query_stage == 3:
            self.exists_checks += 1
            return _FakeQuery(None)
        raise AssertionError("Unexpected extra query")

    def execute(self, statement):
        params = statement.compile().params
        key = (params["event_id"], params["flat_id"], params["reminder_date"])
        if key in self._shared_store.keys:
            return SimpleNamespace(rowcount=0)
        self._shared_store.keys.add(key)
        return SimpleNamespace(rowcount=1)

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("rollback should not be called")


def test_generate_pending_payment_reminders_ignores_db_conflict_on_race(monkeypatch):
    monkeypatch.setattr("app.modules.reminders.reminder_service.date", SimpleNamespace(today=lambda: date(2026, 3, 11)))

    shared_store = _SharedReminderStore()
    first_runner = _FakeSession(shared_store)
    second_runner = _FakeSession(shared_store)

    first_generated = ReminderService.generate_pending_payment_reminders(db=first_runner, event_id="event-1")
    second_generated = ReminderService.generate_pending_payment_reminders(db=second_runner, event_id="event-1")

    assert len(first_generated) == 1
    assert len(second_generated) == 0
    assert len(shared_store.keys) == 1
    assert first_runner.exists_checks == 1
    assert second_runner.exists_checks == 1
