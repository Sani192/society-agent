from app.channels.whatsapp.conversation_fsm import (
    ConversationEvent,
    ConversationState,
    transition,
)


def test_join_transition_happy_path():
    first = transition(ConversationState.IDLE, ConversationEvent.START_JOIN)
    assert first.allowed is True
    assert first.to_state == ConversationState.JOIN_AWAIT_JOIN_CODE

    second = transition(first.to_state, ConversationEvent.PROVIDE_JOIN_CODE)
    assert second.allowed is True
    assert second.to_state == ConversationState.JOIN_AWAIT_FLAT

    third = transition(second.to_state, ConversationEvent.PROVIDE_FLAT)
    assert third.allowed is True
    assert third.to_state == ConversationState.IDLE


def test_blocked_transition():
    blocked = transition(ConversationState.JOIN_AWAIT_JOIN_CODE, ConversationEvent.ENTER_PAYMENT_AMOUNT)
    assert blocked.allowed is False
    assert blocked.to_state == ConversationState.JOIN_AWAIT_JOIN_CODE


def test_cancel_always_returns_idle():
    cancelled = transition(ConversationState.FINANCE_AWAIT_PASS_COUNTS, ConversationEvent.CANCEL)
    assert cancelled.allowed is True
    assert cancelled.to_state == ConversationState.IDLE
