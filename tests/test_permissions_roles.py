from app.permissions.guard import is_action_allowed
from app.permissions.report_guard import ensure_report_access
from app.permissions.roles import ROLE_ACTIONS


def test_committee_member_has_minimal_action_access():
    assert is_action_allowed("committee_member", "SUMMARY") is True
    assert is_action_allowed("committee_member", "PENDING_PAYMENTS") is True
    assert is_action_allowed("committee_member", "ONBOARDING_PENDING") is True


def test_committee_member_is_blocked_from_admin_actions():
    assert is_action_allowed("committee_member", "PAY") is False
    assert is_action_allowed("committee_member", "ADD_EVENT") is False
    assert is_action_allowed("committee_member", "ALL") is False


def test_non_chairman_roles_cannot_manage_committee_members():
    for role in ("secretary", "treasurer", "committee_member"):
        assert is_action_allowed(role, "ADD_COMMITTEE_MEMBER") is False
        assert is_action_allowed(role, "REMOVE_COMMITTEE_MEMBER") is False
        assert is_action_allowed(role, "CHANGE_COMMITTEE_ROLE") is False


def test_committee_member_scope_is_limited_to_intended_actions():
    assert ROLE_ACTIONS["committee_member"] == {"SUMMARY", "PENDING_PAYMENTS", "ONBOARDING_PENDING"}


def test_existing_role_permissions_regression_snapshot_for_operations_and_reports():
    assert "ALL" in ROLE_ACTIONS["chairman"]
    assert {"ADD_EVENT", "ADD_EXPENSE", "OVERRIDE_REPORT", "AUDIT_SUMMARY", "SUMMARY"}.issubset(
        ROLE_ACTIONS["secretary"]
    )
    assert {"PAY", "REFUND", "ADD_SPONSOR", "REFUND_SPONSOR", "SUMMARY"}.issubset(ROLE_ACTIONS["treasurer"])


def test_report_access_rejects_committee_member_exports():
    try:
        ensure_report_access(role="committee_member", report_code="LEDGER")
        assert False, "committee_member should not be able to export ledger"
    except Exception as exc:
        assert "not allowed" in str(exc)


def test_food_pass_operations_report_allows_committee_member():
    ensure_report_access(role="committee_member", report_code="FOOD_PASS_OPERATIONS")
