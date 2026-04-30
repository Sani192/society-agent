from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConversationState(str, Enum):
    IDLE = "IDLE"
    JOIN_AWAIT_JOIN_CODE = "JOIN_AWAIT_JOIN_CODE"
    JOIN_AWAIT_FLAT = "JOIN_AWAIT_FLAT"
    FINANCE_SELECT_EVENT = "FINANCE_SELECT_EVENT"
    FINANCE_AWAIT_CUSTOM_PAYMENT = "FINANCE_AWAIT_CUSTOM_PAYMENT"
    FINANCE_AWAIT_REFUND_REASON = "FINANCE_AWAIT_REFUND_REASON"
    FINANCE_AWAIT_PASS_COUNTS = "FINANCE_AWAIT_PASS_COUNTS"
    APPROVALS_SELECT_REQUEST = "APPROVALS_SELECT_REQUEST"


class ConversationEvent(str, Enum):
    START_JOIN = "START_JOIN"
    PROVIDE_JOIN_CODE = "PROVIDE_JOIN_CODE"
    PROVIDE_FLAT = "PROVIDE_FLAT"
    START_FINANCE = "START_FINANCE"
    SELECT_EVENT = "SELECT_EVENT"
    ENTER_PAYMENT_AMOUNT = "ENTER_PAYMENT_AMOUNT"
    ENTER_REFUND_REASON = "ENTER_REFUND_REASON"
    ENTER_PASS_COUNTS = "ENTER_PASS_COUNTS"
    START_APPROVALS = "START_APPROVALS"
    SELECT_APPROVAL_REQUEST = "SELECT_APPROVAL_REQUEST"
    CANCEL = "CANCEL"
    COMPLETE = "COMPLETE"


_TRANSITIONS: dict[tuple[ConversationState, ConversationEvent], ConversationState] = {
    (ConversationState.IDLE, ConversationEvent.START_JOIN): ConversationState.JOIN_AWAIT_JOIN_CODE,
    (ConversationState.JOIN_AWAIT_JOIN_CODE, ConversationEvent.PROVIDE_JOIN_CODE): ConversationState.JOIN_AWAIT_FLAT,
    (ConversationState.JOIN_AWAIT_FLAT, ConversationEvent.PROVIDE_FLAT): ConversationState.IDLE,
    (ConversationState.IDLE, ConversationEvent.START_FINANCE): ConversationState.FINANCE_SELECT_EVENT,
    (ConversationState.FINANCE_SELECT_EVENT, ConversationEvent.SELECT_EVENT): ConversationState.FINANCE_SELECT_EVENT,
    (ConversationState.FINANCE_AWAIT_CUSTOM_PAYMENT, ConversationEvent.ENTER_PAYMENT_AMOUNT): ConversationState.IDLE,
    (ConversationState.FINANCE_AWAIT_REFUND_REASON, ConversationEvent.ENTER_REFUND_REASON): ConversationState.IDLE,
    (ConversationState.FINANCE_AWAIT_PASS_COUNTS, ConversationEvent.ENTER_PASS_COUNTS): ConversationState.FINANCE_AWAIT_PASS_COUNTS,
    (ConversationState.IDLE, ConversationEvent.START_APPROVALS): ConversationState.APPROVALS_SELECT_REQUEST,
    (ConversationState.APPROVALS_SELECT_REQUEST, ConversationEvent.SELECT_APPROVAL_REQUEST): ConversationState.IDLE,
}


@dataclass(frozen=True)
class TransitionResult:
    allowed: bool
    from_state: ConversationState
    event: ConversationEvent
    to_state: ConversationState


def transition(state: ConversationState, event: ConversationEvent) -> TransitionResult:
    if event in {ConversationEvent.CANCEL, ConversationEvent.COMPLETE}:
        return TransitionResult(True, state, event, ConversationState.IDLE)
    next_state = _TRANSITIONS.get((state, event))
    if next_state is None:
        return TransitionResult(False, state, event, state)
    return TransitionResult(True, state, event, next_state)
