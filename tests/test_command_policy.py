from app.permissions.command_policy import get_intent_state_warning


def test_non_committee_payment_blocked_in_draft():
    warning = get_intent_state_warning(intent="PAY", event_state="DRAFT", is_committee=False)
    assert warning


def test_non_committee_payment_allowed_in_active():
    warning = get_intent_state_warning(intent="PAY", event_state="ACTIVE", is_committee=False)
    assert warning is None


def test_committee_start_event_only_locked():
    assert get_intent_state_warning(intent="START_EVENT", event_state="ACTIVE", is_committee=True)
    assert get_intent_state_warning(intent="START_EVENT", event_state="LOCKED", is_committee=True) is None


def test_committee_report_options_allowed_closed():
    assert get_intent_state_warning(intent="REPORT_OPTIONS", event_state="CLOSED", is_committee=True) is None
