import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.models import (
    AuditLog,
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
    WorkflowState,
)
from app.modules.contributions.contribution_refund_service import ContributionRefundService
from app.modules.contributions.contribution_service import ContributionService
from app.modules.events.service import EventService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.modules.users.channel_identity_service import link_member_by_code


FIXTURE_PATH = Path("tests/fixtures/workflow_smoke_data.json")
DATA = json.loads(FIXTURE_PATH.read_text())
IDS = DATA["ids"]


class QueryStub:
    def __init__(self, first_result=None, all_result=None, count_result=0, scalar_result=0):
        self.first_result = first_result
        self.all_result = all_result if all_result is not None else []
        self.count_result = count_result
        self.scalar_result = scalar_result

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_result

    def all(self):
        return self.all_result

    def count(self):
        return self.count_result

    def scalar(self):
        return self.scalar_result


class FakeDB:
    def __init__(self, query_plan):
        self.query_plan = {k: list(v) for k, v in query_plan.items()}
        self.added = []
        self.commits = 0

    def query(self, model):
        planned = self.query_plan.get(model, [])
        if planned:
            return planned.pop(0)
        return QueryStub()

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = f"id-{len(self.added)+1}"
        self.added.append(obj)

    def flush(self):
        return None

    def refresh(self, _):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None


def _base_entities():
    society = SimpleNamespace(id=IDS["society_id"], name="Smoke Society")
    chairman = SimpleNamespace(
        id=IDS["chairman_id"],
        society_id=IDS["society_id"],
        name="Chairman Smoke",
        role="chairman",
        is_active=True,
        phone_number="919876543210",
    )
    flat = SimpleNamespace(id=IDS["flat_id"], society_id=IDS["society_id"], is_active=True)
    return society, chairman, flat


@pytest.mark.smoke
def test_member_link_code_login_workflow_e2e():
    cfg = DATA["workflows"]["member_link_code_login"]
    expected = cfg["expected"]
    _, chairman, _ = _base_entities()
    link_code = SimpleNamespace(
        committee_member_id=chairman.id,
        committee_member=chairman,
        code=cfg["link_code"],
        consumed_at=None,
    )
    identity_query = QueryStub(first_result=None)
    db = FakeDB(
        {
            CommitteeMemberLinkCode: [QueryStub(first_result=link_code)],
            CommitteeMemberChannelIdentity: [identity_query],
        }
    )

    linked_member = link_member_by_code(
        db=db,
        channel_type=cfg["channel_type"],
        sender_id=cfg["sender_id"],
        code=cfg["link_code"],
        phone_number=cfg["phone_number"],
        username=cfg["username"],
    )

    identities = [x for x in db.added if isinstance(x, CommitteeMemberChannelIdentity)]
    assert linked_member.name == expected["member_name"]
    assert len(identities) == expected["identity_count"]
    assert (link_code.consumed_at is not None) == expected["code_consumed"]


@pytest.mark.smoke
def test_create_event_workflow_e2e():
    cfg = DATA["workflows"]["create_event"]
    expected = cfg["expected"]
    society, chairman, _ = _base_entities()
    db = FakeDB({})

    event = EventService.create_event(
        db,
        society_id=society.id,
        name=cfg["name"],
        event_date=datetime.fromisoformat(cfg["event_date"]),
        food_types=cfg["food_types"],
        created_by=chairman.id,
        charge_per_adult=cfg["charge_per_adult"],
        charge_per_child=cfg["charge_per_child"],
    )

    workflow = next(x for x in db.added if isinstance(x, WorkflowState))
    create_audit = next(x for x in db.added if isinstance(x, AuditLog) and x.action == expected["audit_action"])

    assert event.status == expected["event_status"]
    assert workflow.current_state == expected["workflow_state"]
    assert workflow.allowed_next_states == expected["allowed_next"]
    assert create_audit is not None


@pytest.mark.smoke
def test_event_publish_path_workflow_e2e():
    cfg = DATA["workflows"]["event_publish_path"]
    expected = cfg["expected"]
    society, chairman, _ = _base_entities()
    event = Event(id=IDS["event_id"], society_id=society.id, status="DRAFT")
    workflow = WorkflowState(event_id=event.id, current_state="DRAFT", allowed_next_states=["ACTIVE"])

    db = FakeDB(
        {
            Event: [QueryStub(first_result=event)] * 4,
            WorkflowState: [QueryStub(first_result=workflow)] * 4,
            # Workflow checks lookup current state + member
            CommitteeMemberLinkCode: [],
        }
    )
    db.query_plan.setdefault(WorkflowState, []).extend([QueryStub(first_result=workflow)] * 4)
    db.query_plan.setdefault(type(chairman), [])
    from app.db.models import CommitteeMember

    db.query_plan[CommitteeMember] = [QueryStub(first_result=chairman)] * 4

    EventService.activate_event(db, event_id=event.id, performed_by=chairman.id)
    EventService.lock_passes(db, event_id=event.id, performed_by=chairman.id)
    EventService.start_event_day(db, event_id=event.id, performed_by=chairman.id)
    EventService.close_event(db, event_id=event.id, performed_by=chairman.id, reason=cfg["close_reason"])

    actions = [x.action for x in db.added if isinstance(x, AuditLog)]
    assert event.status == expected["event_status"]
    assert workflow.current_state == expected["workflow_state"]
    assert workflow.allowed_next_states == expected["allowed_next"]
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_payment_request_approval_workflow_e2e():
    cfg = DATA["workflows"]["payment_request_approval"]
    expected = cfg["expected"]
    society, chairman, flat = _base_entities()
    event = SimpleNamespace(id=IDS["event_id"], society_id=society.id)
    workflow = WorkflowState(event_id=event.id, current_state="ACTIVE", allowed_next_states=[])
    food_pass = SimpleNamespace(total_amount=cfg["request_amount"], is_participating=True)
    payment_request = QueryStub(first_result=None)

    from app.db.models import CommitteeMember

    db = FakeDB(
        {
            Event: [QueryStub(first_result=event), QueryStub(first_result=event)],
            Flat: [QueryStub(first_result=flat), QueryStub(first_result=flat)],
            WorkflowState: [QueryStub(first_result=workflow), QueryStub(first_result=workflow)],
            CommitteeMember: [QueryStub(first_result=chairman), QueryStub(first_result=chairman)],
            EventFoodPass: [QueryStub(first_result=food_pass), QueryStub(first_result=food_pass)],
            PaymentRequest: [payment_request, QueryStub(count_result=0)],
            Payment: [QueryStub(first_result=None)],
        }
    )

    request = PaymentRequestService.request_payment(
        db,
        event_id=event.id,
        flat_id=flat.id,
        amount=cfg["request_amount"],
        payment_mode=cfg["payment_mode"],
        requested_by=cfg["requested_by"],
    )
    payment = PaymentRequestService.approve_request(db, request=request, performed_by=chairman.id)

    request.status = "approved"
    actions = [x.action for x in db.added if isinstance(x, AuditLog)]
    assert request.status == expected["request_status"]
    assert payment.status == expected["payment_status"]
    assert payment.paid_amount == expected["paid_amount"]
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_refund_request_approval_workflow_e2e():
    cfg = DATA["workflows"]["refund_request_approval"]
    expected = cfg["expected"]
    society, chairman, flat = _base_entities()
    event = SimpleNamespace(id=IDS["event_id"], society_id=society.id)
    workflow = WorkflowState(event_id=event.id, current_state="ACTIVE", allowed_next_states=[])
    payment_row = Payment(event_id=event.id, flat_id=flat.id, expected_amount=400, paid_amount=400, status="paid")

    from app.db.models import CommitteeMember

    db = FakeDB(
        {
            Event: [QueryStub(first_result=event), QueryStub(first_result=event)],
            Flat: [QueryStub(first_result=flat), QueryStub(first_result=flat)],
            WorkflowState: [QueryStub(first_result=workflow), QueryStub(first_result=workflow)],
            CommitteeMember: [QueryStub(first_result=chairman), QueryStub(first_result=chairman)],
            Payment: [QueryStub(first_result=payment_row), QueryStub(first_result=payment_row)],
            RefundRequest: [QueryStub(first_result=None), QueryStub(count_result=0)],
            Refund: [QueryStub(all_result=[])],
        }
    )

    request = RefundRequestService.request_refund(
        db,
        event_id=event.id,
        flat_id=flat.id,
        amount=cfg["refund_amount"],
        reason=cfg["reason"],
        requested_by=cfg["requested_by"],
    )
    refund = RefundRequestService.approve_request(db, request=request, performed_by=chairman.id)

    request.status = "approved"
    actions = [x.action for x in db.added if isinstance(x, AuditLog)]
    assert request.status == expected["request_status"]
    assert refund.status == expected["refund_status"]
    assert payment_row.status == expected["payment_status"]
    for action in expected["audit_actions"]:
        assert action in actions


@pytest.mark.smoke
def test_contribution_refund_workflow_e2e():
    cfg = DATA["workflows"]["contribution_refund"]
    expected = cfg["expected"]
    society, chairman, _ = _base_entities()
    event = SimpleNamespace(id=IDS["event_id"], society_id=society.id)
    workflow = WorkflowState(event_id=event.id, current_state="ACTIVE", allowed_next_states=[])

    contribution = EventContribution(
        id="contrib-1",
        event_id=event.id,
        society_id=society.id,
        contribution_code="SP-001",
        contribution_type="sponsor",
        source_name=cfg["source_name"],
        amount=cfg["amount"],
    )

    from app.db.models import CommitteeMember

    db = FakeDB(
        {
            Event: [QueryStub(first_result=event), QueryStub(first_result=event)],
            WorkflowState: [QueryStub(first_result=workflow), QueryStub(first_result=workflow)],
            CommitteeMember: [QueryStub(first_result=chairman), QueryStub(first_result=chairman)],
            EventContribution: [QueryStub(count_result=0), QueryStub(first_result=contribution)],
            ContributionRefund: [QueryStub(scalar_result=0)],
        }
    )

    contribution_code = ContributionService.add_contribution(
        db,
        event_id=event.id,
        society_id=society.id,
        contribution_type=cfg["contribution_type"],
        source_name=cfg["source_name"],
        amount=cfg["amount"],
        performed_by=chairman.id,
        notes="Smoke contribution",
    )
    ContributionRefundService.process_refund(
        db,
        event_id=event.id,
        contribution_code=contribution.contribution_code,
        amount=cfg["refund_amount"],
        reason=cfg["refund_reason"],
        performed_by=chairman.id,
    )

    refund = next(x for x in db.added if isinstance(x, ContributionRefund))
    actions = [x.action for x in db.added if isinstance(x, AuditLog)]
    assert contribution_code == expected["contribution_code"]
    assert refund.status == expected["refund_status"]
    for action in expected["audit_actions"]:
        assert action in actions
