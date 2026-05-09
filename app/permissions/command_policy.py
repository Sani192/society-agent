from __future__ import annotations

ACTIVE_EVENT_STATES = {"ACTIVE", "LOCKED", "EVENT_DAY"}

NON_COMMITTEE_ACTIVE_ONLY_INTENTS = {
    "ADD_PASS",
    "PAY",
    "REFUND",
}

COMMITTEE_INTENT_ALLOWED_STATES: dict[str, set[str]] = {
    "ADD_EVENT": {"DRAFT"},
    "ACTIVATE_EVENT": {"DRAFT"},
    "LOCK_PASSES": {"ACTIVE"},
    "START_EVENT": {"LOCKED"},
    "CLOSE_EVENT": {"EVENT_DAY"},
    "ADD_EXPENSE": ACTIVE_EVENT_STATES,
    "ADD_SPONSOR": ACTIVE_EVENT_STATES,
    "REFUND_SPONSOR": ACTIVE_EVENT_STATES,
    "REMIND_FLAT": ACTIVE_EVENT_STATES,
    "PENDING_PAYMENTS": ACTIVE_EVENT_STATES,
    "PAYMENT_REQUESTS": ACTIVE_EVENT_STATES,
    "REFUND_REQUESTS": ACTIVE_EVENT_STATES,
    "APPROVE_PAYMENT": ACTIVE_EVENT_STATES,
    "APPROVE_REFUND": ACTIVE_EVENT_STATES,
    "REPORT_OPTIONS": {"DRAFT", "ACTIVE", "LOCKED", "EVENT_DAY", "CLOSED"},
    "EXPORT_SELECTION": {"DRAFT", "ACTIVE", "LOCKED", "EVENT_DAY", "CLOSED"},
    "PARTICIPATION_REPORT": {"DRAFT", "ACTIVE", "LOCKED", "EVENT_DAY", "CLOSED"},
    "GENERATE_FOOD_TOKENS": {"LOCKED", "EVENT_DAY"},
    "OPEN_FOOD_COUNTER": {"EVENT_DAY"},
    "VERIFY_FOOD_TOKEN": {"EVENT_DAY"},
    "SCAN_FOOD_QR": {"EVENT_DAY"},
    "SERVE_FOOD_FLAT": {"EVENT_DAY"},
    "FLAT_PASS_STATUS": {"EVENT_DAY"},
    "TOKEN_STATUS": {"EVENT_DAY"},
    "FOOD_DASHBOARD": {"EVENT_DAY"},
}


STATE_WARNINGS = {
    "ADD_PASS": "Pass updates are available only when event is active.",
    "PAY": "Payment actions are available only when event is active.",
    "REFUND": "Refund actions are available only when event is active.",
    "REPORT_OPTIONS": "Reports are available only when event is active.",
    "EXPORT_SELECTION": "Reports are available only when event is active.",
}


def get_event_state(event) -> str | None:
    return (getattr(event, "status", None) or "").upper() or None


def get_intent_state_warning(*, intent: str, event_state: str | None, is_committee: bool) -> str | None:
    if intent == "MENU":
        return None

    if is_committee:
        allowed_states = COMMITTEE_INTENT_ALLOWED_STATES.get(intent)
        if not allowed_states or event_state is None:
            return None
        if event_state in allowed_states:
            return None
        allowed = ", ".join(sorted(allowed_states))
        return f"This command is available only when event state is: {allowed}."

    if event_state is None:
        return None

    if intent in NON_COMMITTEE_ACTIVE_ONLY_INTENTS and event_state not in ACTIVE_EVENT_STATES:
        return STATE_WARNINGS.get(intent, "This command is available only when event is active.")

    return None


def is_member_action_visible(*, intent: str, event_state: str | None, is_committee: bool) -> bool:
    return get_intent_state_warning(intent=intent, event_state=event_state, is_committee=is_committee) is None


def member_action_state_warning(*, intent: str, event_state: str | None) -> str | None:
    return get_intent_state_warning(intent=intent, event_state=event_state, is_committee=False)
