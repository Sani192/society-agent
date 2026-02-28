from types import SimpleNamespace
from uuid import uuid4

from app.channels.whatsapp.client import WhatsAppRetryableError
from app.modules.announcements import delivery_worker
from app.modules.announcements.recipient_service import AnnouncementRecipientService
from app.modules.announcements.service import AnnouncementService


class _DummyResponse:
    status_code = 429


class _UpdateQuery:
    def filter(self, *args, **kwargs):
        return self

    def update(self, *args, **kwargs):
        return 1


class _SummaryQuery:
    def __init__(self):
        self._announcement_id = None

    def options(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return [("sent", 1)]

    def group_by(self, *args, **kwargs):
        return self


class _PendingQuery(_SummaryQuery):
    def __init__(self, deliveries):
        super().__init__()
        self.deliveries = deliveries

    def all(self):
        return self.deliveries


class _FakeDB:
    def __init__(self, deliveries):
        self.pending_query = _PendingQuery(deliveries)
        self.summary_query = _SummaryQuery()
        self.update_query = _UpdateQuery()
        self.commit_count = 0
        self.closed = False

    def query(self, *args, **kwargs):
        if len(args) > 1:
            return self.summary_query
        first = args[0]
        if getattr(first, "__name__", None) == "AnnouncementDelivery":
            return self.pending_query
        if getattr(first, "__name__", None) == "Announcement":
            return self.update_query
        return self.summary_query

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


def _delivery(status="pending"):
    announcement_id = uuid4()
    return SimpleNamespace(
        announcement_id=announcement_id,
        member_identity_id=uuid4(),
        status=status,
        sent_at=None,
        attempts=0,
        channel="whatsapp",
        recipient_id="919999000000",
        rendered_payload={
            "template_name": "society_announcement_general",
            "body_parameters": ["Resident", "Notice"],
        },
        member_identity=SimpleNamespace(metadata_json={"channel_state": {"whatsapp": {"opt_in": True}}}),
        announcement=SimpleNamespace(
            id=announcement_id,
            society_id=uuid4(),
            event_id=None,
            message_text="Notice",
            type="announcement",
        ),
        last_error=None,
    )


def test_recipient_segmentation_deduplicates_and_skips_missing_whatsapp():
    rows = [
        SimpleNamespace(id=uuid4(), whatsapp_user_id="91911", owner_name="A", normalized_identifier="A-1", event_name="E"),
        SimpleNamespace(id=uuid4(), whatsapp_user_id="91911", owner_name="B", normalized_identifier="B-1", event_name="E"),
        SimpleNamespace(id=uuid4(), whatsapp_user_id=None, owner_name="C", normalized_identifier="C-1", event_name="E"),
    ]

    result = AnnouncementRecipientService._resolve_whatsapp_targets(rows)

    assert result["total_candidates"] == 3
    assert result["queued_count"] == 1
    assert result["duplicate_whatsapp_ids"] == 1
    assert result["skipped_missing_whatsapp"] == 1


def test_rate_limit_retry_uses_retry_after(monkeypatch):
    delivery = _delivery()
    db = _FakeDB([delivery])
    monkeypatch.setattr(delivery_worker, "SessionLocal", lambda: db)
    sleeps = []
    monkeypatch.setattr(delivery_worker.time, "sleep", lambda value: sleeps.append(value))

    state = {"attempt": 0}

    def _send(d):
        state["attempt"] += 1
        if state["attempt"] == 1:
            raise WhatsAppRetryableError("retry", response=_DummyResponse(), retry_after_seconds=1.75)
        return "sent_template", None

    monkeypatch.setattr(delivery_worker, "_send_delivery", _send)

    processed = delivery_worker.run_pending_announcement_deliveries(batch_size=1, send_interval_seconds=0)

    assert processed == 1
    assert any(abs(value - 1.75) < 1e-9 for value in sleeps)


def test_policy_gating_outside_24h_uses_template(monkeypatch):
    sent = []

    class _Client:
        def send_template_message(self, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr(delivery_worker, "get_whatsapp_client", lambda: _Client())

    delivery = _delivery()
    outcome, reason = delivery_worker._send_delivery(delivery)

    assert outcome == "sent_template"
    assert reason is None
    assert len(sent) == 1


def test_dispatch_is_idempotent_for_already_sent_delivery(monkeypatch):
    delivery = _delivery(status="sent")
    delivery.sent_at = object()
    db = _FakeDB([delivery])
    monkeypatch.setattr(delivery_worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(delivery_worker, "_send_delivery", lambda d: (_ for _ in ()).throw(AssertionError("must not send")))

    processed = delivery_worker.run_pending_announcement_deliveries(batch_size=1)

    assert processed == 0


def test_create_announcement_writes_audit_log(db_session):
    AnnouncementService.create_announcement(
        db_session,
        society_id=uuid4(),
        event_id=None,
        announcement_type="announcement",
        message_text="Short notice for all members",
        created_by=uuid4(),
        recipients=[],
    )

    audit_rows = [call.args[0] for call in db_session.add.call_args_list if call.args[0].__class__.__name__ == "AuditLog"]
    assert len(audit_rows) == 1
    assert audit_rows[0].entity_type == "announcement"
    assert audit_rows[0].action == "CREATE_ANNOUNCEMENT"
    assert "type=announcement" in (audit_rows[0].reason or "")
