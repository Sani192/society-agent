from app.permissions.guard import is_action_allowed
from app.permissions.report_guard import ensure_report_access


def test_committee_member_has_minimal_action_access():
    assert is_action_allowed("committee_member", "SUMMARY") is True
    assert is_action_allowed("committee_member", "PENDING_PAYMENTS") is True
    assert is_action_allowed("committee_member", "ONBOARDING_PENDING") is True


def test_committee_member_is_blocked_from_admin_actions():
    assert is_action_allowed("committee_member", "PAY") is False
    assert is_action_allowed("committee_member", "ADD_EVENT") is False
    assert is_action_allowed("committee_member", "ALL") is False


def test_report_access_rejects_committee_member_exports():
    try:
        ensure_report_access(role="committee_member", report_code="LEDGER")
        assert False, "committee_member should not be able to export ledger"
    except Exception as exc:
        assert "not allowed" in str(exc)
