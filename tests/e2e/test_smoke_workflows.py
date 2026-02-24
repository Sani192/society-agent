import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.api.health import health_check
from app.api.reports.financial import event_summary
from app.api.telegram import telegram_webhook_event
from app.api.whatsapp import whatsapp_webhook_event
from app.db.base import Base
from app.db.models import (
    AuditLog,
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    CommitteeMemberLinkCode,
    ContributionRefund,
    Event,
    EventContribution,
    EventFoodPass,
    Flat,
    Payment,
    PaymentRequest,
    Refund,
    RefundRequest,
    Society,
    UserFlatMapping,
    WorkflowState,
)
from app.modules.contributions.contribution_refund_service import ContributionRefundService
from app.modules.contributions.contribution_service import ContributionService
from app.modules.events.service import EventService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService


FIXTURE_PATH = Path("tests/fixtures/workflow_smoke_data.json")
DATA = json.loads(FIXTURE_PATH.read_text())
IDS = DATA["ids"]


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_element, _compiler, **_kwargs):
    return "JSON"


@compiles(PGUUID, "sqlite")
def _compile_uuid_sqlite(_element, _compiler, **_kwargs):
    return "CHAR(36)"


class StubRequest:
    def __init__(self, payload: dict, *, body: bytes | None = None, headers: dict | None = None):
        self._payload = payload
        self._body = body if body is not None else json.dumps(payload).encode("utf-8")
        self.headers = headers or {}

    async def body(self):
        return self._body

    async def json(self):
        return self._payload


@pytest.fixture
def smoke_db(tmp_path, monkeypatch):
    db_file = tmp_path / "workflow_smoke.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr("app.db.session.engine", engine)
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.channels.core.handler.SessionLocal", TestingSessionLocal)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _seed_base_entities(db):
    society = Society(
        id=UUID(IDS["society_id"]),
        name="Smoke Society",
        city="Test City",
        state="Test State",
        config_json={"branding": {}},
        is_active=True,
    )
    chairman = CommitteeMember(
        id=UUID(IDS["chairman_id"]),
        society_id=society.id,
        name="Chairman Smoke",
        role="chairman",
        is_active=True,
        phone_number="919876543210",
    )
    flat = Flat(
        id=UUID(IDS["flat_id"]),
        society_id=society.id,
        flat_number="A-101",
        block="A",
        owner_name="Resident Smoke",
        is_active=True,
    )
    mapping = UserFlatMapping(
        society_id=society.id,
        flat_id=flat.id,
        user_identifier=chairman.phone_number,
        role="owner",
        is_active=True,
    )

    db.add_all([society, chairman, flat, mapping])
    db.commit()
    return society, chairman, flat


@pytest.mark.smoke
def test_health_route_smoke():
    response = health_check()
    assert response == {"status": "ok", "message": "Society Agent running locally"}


@pytest.mark.smoke
def test_member_link_code_login_workflow_e2e(smoke_db, monkeypatch):
    cfg = DATA["workflows"]["member_link_code_login"]
    expected = cfg["expected"]
    _, chairman, _ = _seed_base_entities(smoke_db)

    smoke_db.add(
        CommitteeMemberLinkCode(
            committee_member_id=chairman.id,
            code=cfg["link_code"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
    )
    smoke_db.commit()

    monkeypatch.setattr("app.api.telegram._verify_webhook_secret", lambda secret: None)

    delivered = []

    class StubTelegramClient:
        def send_text_message(self, chat_id, text):
            delivered.append((chat_id, text))

    monkeypatch.setattr("app.api.telegram.get_telegram_client", lambda: StubTelegramClient())

    from app.channels.core.handler import handle_inbound_message as real_handle_inbound_message
    monkeypatch.setattr(
        "app.api.telegram.handle_inbound_message",
        lambda message: real_handle_inbound_message(message, session_factory=lambda: smoke_db),
    )

    payload = {
        "update_id": 100001,
        "message": {
            "message_id": 55,
            "date": 1700000000,
            "chat": {"id": 99901, "type": "private"},
            "from": {
                "id": int(cfg["sender_id"].split("-")[-1]),
                "is_bot": False,
                "username": cfg["username"],
                "first_name": "Chairman",
            },
            "text": f"link member {cfg['link_code']}",
        },
    }

    response = asyncio.run(telegram_webhook_event(StubRequest(payload), x_telegram_bot_api_secret_token=None))

    assert response == {"status": "ok"}
    assert delivered and "linked successfully" in delivered[0][1]

    identity_rows = smoke_db.query(CommitteeMemberChannelIdentity).all()
    link_code = smoke_db.query(CommitteeMemberLinkCode).filter_by(code=cfg["link_code"]).first()
    assert len(identity_rows) == expected["identity_count"]
    assert identity_rows[0].committee_member_id == chairman.id
    assert identity_rows[0].external_user_id == str(int(cfg["sender_id"].split("-")[-1]))
    assert link_code.consumed_at is not None


@pytest.mark.smoke
def test_create_event_workflow_e2e(smoke_db):
    cfg = DATA["workflows"]["create_event"]
    expected = cfg["expected"]
    society, chairman, _ = _seed_base_entities(smoke_db)

    event = EventService.create_event(
        smoke_db,
        society_id=society.id,
        name=cfg["name"],
        event_date=datetime.fromisoformat(cfg["event_date"]),
        food_types=cfg["food_types"],
        created_by=chairman.id,
        charge_per_adult=cfg["charge_per_adult"],
        charge_per_child=cfg["charge_per_child"],
    )

    persisted = smoke_db.query(Event).filter_by(id=event.id).first()
    workflow = smoke_db.query(WorkflowState).filter_by(event_id=event.id).first()
    create_audit = smoke_db.query(AuditLog).filter_by(entity_id=event.id, action=expected["audit_action"]).first()

    assert persisted.status == expected["event_status"]
    assert workflow.current_state == expected["workflow_state"]
    assert workflow.allowed_next_states == expected["allowed_next"]
    assert create_audit is not None


@pytest.mark.smoke
def test_event_publish_path_workflow_e2e(smoke_db):
    cfg = DATA["workflows"]["event_publish_path"]
    expected = cfg["expected"]
    society, chairman, _ = _seed_base_entities(smoke_db)

    event = EventService.create_event(
        smoke_db,
        society_id=society.id,
        name="Lifecycle Event",
        event_date=datetime(2026, 3, 12, 11, 0, 0),
        food_types=["veg"],
        created_by=chairman.id,
        charge_per_adult=200,
        charge_per_child=100,
    )

    EventService.activate_event(smoke_db, event_id=event.id, performed_by=chairman.id)
    EventService.lock_passes(smoke_db, event_id=event.id, performed_by=chairman.id)
    EventService.start_event_day(smoke_db, event_id=event.id, performed_by=chairman.id)
    EventService.close_event(smoke_db, event_id=event.id, performed_by=chairman.id, reason=cfg["close_reason"])

    persisted = smoke_db.query(Event).filter_by(id=event.id).first()
    workflow = smoke_db.query(WorkflowState).filter_by(event_id=event.id).first()
    actions = {row.action for row in smoke_db.query(AuditLog).filter(AuditLog.entity_id == event.id).all()}

    assert persisted.status == expected["event_status"]
    assert workflow.current_state == expected["workflow_state"]
    assert workflow.allowed_next_states == expected["allowed_next"]
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_payment_request_approval_workflow_e2e(smoke_db):
    cfg = DATA["workflows"]["payment_request_approval"]
    expected = cfg["expected"]
    society, chairman, flat = _seed_base_entities(smoke_db)

    event = EventService.create_event(
        smoke_db,
        society_id=society.id,
        name="Payments Event",
        event_date=datetime(2026, 3, 13, 12, 0, 0),
        food_types=["veg", "jain"],
        created_by=chairman.id,
        charge_per_adult=250,
        charge_per_child=100,
    )
    EventService.activate_event(smoke_db, event_id=event.id, performed_by=chairman.id)

    smoke_db.add(
        EventFoodPass(
            event_id=event.id,
            flat_id=flat.id,
            veg_count=2,
            jain_count=0,
            kids_count=0,
            total_amount=cfg["request_amount"],
            is_participating=True,
        )
    )
    smoke_db.commit()

    requester_mapping = (
        smoke_db.query(UserFlatMapping)
        .filter_by(society_id=society.id, flat_id=flat.id, is_active=True)
        .first()
    )
    assert requester_mapping is not None

    request = PaymentRequestService.request_payment(
        smoke_db,
        event_id=event.id,
        flat_id=flat.id,
        amount=cfg["request_amount"],
        payment_mode=cfg["payment_mode"],
        requested_by_mapping_id=requester_mapping.id,
    )
    payment = PaymentRequestService.approve_request(smoke_db, request=request, performed_by=chairman.id)

    persisted_request = smoke_db.query(PaymentRequest).filter_by(id=request.id).first()
    persisted_payment = smoke_db.query(Payment).filter_by(id=payment.id).first()
    actions = {row.action for row in smoke_db.query(AuditLog).filter_by(society_id=society.id).all()}

    assert persisted_request.status == expected["request_status"]
    assert persisted_payment.status == expected["payment_status"]
    assert persisted_payment.paid_amount == expected["paid_amount"]
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_refund_request_approval_workflow_e2e(smoke_db):
    cfg = DATA["workflows"]["refund_request_approval"]
    expected = cfg["expected"]
    society, chairman, flat = _seed_base_entities(smoke_db)

    event = EventService.create_event(
        smoke_db,
        society_id=society.id,
        name="Refunds Event",
        event_date=datetime(2026, 3, 14, 12, 0, 0),
        food_types=["veg"],
        created_by=chairman.id,
        charge_per_adult=250,
        charge_per_child=100,
    )
    EventService.activate_event(smoke_db, event_id=event.id, performed_by=chairman.id)

    smoke_db.add(
        Payment(
            event_id=event.id,
            flat_id=flat.id,
            expected_amount=400,
            paid_amount=400,
            status="paid",
            payment_mode="upi",
        )
    )
    smoke_db.commit()

    requester_mapping = (
        smoke_db.query(UserFlatMapping)
        .filter_by(society_id=society.id, flat_id=flat.id, is_active=True)
        .first()
    )
    assert requester_mapping is not None

    request = RefundRequestService.request_refund(
        smoke_db,
        event_id=event.id,
        flat_id=flat.id,
        amount=cfg["refund_amount"],
        reason=cfg["reason"],
        requested_by_mapping_id=requester_mapping.id,
    )
    refund = RefundRequestService.approve_request(smoke_db, request=request, performed_by=chairman.id)

    persisted_request = smoke_db.query(RefundRequest).filter_by(id=request.id).first()
    persisted_refund = smoke_db.query(Refund).filter_by(id=refund.id).first()
    payment_row = smoke_db.query(Payment).filter_by(event_id=event.id, flat_id=flat.id).first()
    actions = {row.action for row in smoke_db.query(AuditLog).filter_by(society_id=society.id).all()}

    assert persisted_request.status == expected["request_status"]
    assert persisted_refund.status == expected["refund_status"]
    assert payment_row.status == expected["payment_status"]
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_contribution_refund_workflow_e2e(smoke_db):
    cfg = DATA["workflows"]["contribution_refund"]
    expected = cfg["expected"]
    society, chairman, _ = _seed_base_entities(smoke_db)

    event = EventService.create_event(
        smoke_db,
        society_id=society.id,
        name="Contribution Event",
        event_date=datetime(2026, 3, 15, 12, 0, 0),
        food_types=["veg"],
        created_by=chairman.id,
        charge_per_adult=200,
        charge_per_child=100,
    )
    EventService.activate_event(smoke_db, event_id=event.id, performed_by=chairman.id)

    contribution_code = ContributionService.add_contribution(
        smoke_db,
        event_id=event.id,
        society_id=society.id,
        contribution_type=cfg["contribution_type"],
        source_name=cfg["source_name"],
        amount=cfg["amount"],
        performed_by=chairman.id,
        notes="Smoke contribution",
    )
    ContributionRefundService.process_refund(
        smoke_db,
        event_id=event.id,
        contribution_code=contribution_code,
        amount=cfg["refund_amount"],
        reason=cfg["refund_reason"],
        performed_by=chairman.id,
    )

    report_response = event_summary(phone=chairman.phone_number, event_id=event.id, db=smoke_db)

    refund = smoke_db.query(ContributionRefund).first()
    contribution = smoke_db.query(EventContribution).filter_by(contribution_code=contribution_code).first()
    actions = {row.action for row in smoke_db.query(AuditLog).filter_by(society_id=society.id).all()}

    assert isinstance(report_response, str)
    assert report_response.startswith("✅")
    assert contribution.contribution_code == expected["contribution_code"]
    assert refund.status == expected["refund_status"]
    assert any(action.startswith("VIEW_EVENT_FINANCIAL_SUMMARY") for action in actions)
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_whatsapp_webhook_smoke(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)

    secret = "smoke-secret"
    monkeypatch.setattr("app.api.whatsapp.settings.WHATSAPP_APP_SECRET", secret)

    payload = {"object": "whatsapp_business_account", "entry": []}
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    response = asyncio.run(
        whatsapp_webhook_event(
            StubRequest(payload, body=body, headers={"X-Hub-Signature-256": f"sha256={signature}"})
        )
    )

    assert response == {"status": "ignored"}
