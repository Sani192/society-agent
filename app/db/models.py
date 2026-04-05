#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:22:14 2026

@author: anonymous
"""

# app/db/models.py

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    Date,
    Text,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Society(Base):
    __tablename__ = "societies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)

    timezone = Column(String(50), nullable=False, default="Asia/Kolkata")

    # Society-level configuration (food types, language, rules, etc.)
    config_json = Column(JSONB, nullable=False, default=dict)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommitteeMember(Base):
    __tablename__ = "committee_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    society_id = Column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(String(255), nullable=False)

    phone_number = Column(String(20), nullable=False, unique=True)

    role = Column(
        String(50),
        nullable=False
        # chairman | secretary | treasurer | committee_member
    )

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    society = relationship("Society", backref="committee_members")


class CommitteeMemberChannelIdentity(Base):
    __tablename__ = "committee_member_channel_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    committee_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committee_members.id", ondelete="CASCADE"),
        nullable=False
    )

    channel_type = Column(String(50), nullable=False, index=True)
    external_user_id = Column(String(255), nullable=True, index=True)
    username = Column(String(255), nullable=True, index=True)

    is_verified = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("channel_type", "external_user_id", name="uq_channel_external_user"),
    )

    committee_member = relationship("CommitteeMember", backref="channel_identities")


class ChannelConversation(Base):
    __tablename__ = "channel_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    channel = Column(String(20), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    chat_id_or_phone = Column(String(255), nullable=True)

    first_occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("channel", "external_user_id", name="uq_channel_conversation_user"),
        CheckConstraint("channel IN ('whatsapp', 'telegram')", name="ck_channel_conversations_channel"),
        Index("ix_channel_conversations_channel_external_user", "channel", "external_user_id"),
    )


class ChannelMessageEvent(Base):
    __tablename__ = "channel_message_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    trace_id = Column(String(255), nullable=True, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    channel = Column(String(20), nullable=False)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=True, index=True)
    direction = Column(String(20), nullable=False)
    event_type = Column(String(50), nullable=False)

    provider_message_id = Column(String(255), nullable=True)
    provider_update_id = Column(String(255), nullable=True)
    chat_id_or_phone = Column(String(255), nullable=True)
    external_user_id = Column(String(255), nullable=True)

    message_text_raw = Column(Text, nullable=True)
    message_text_raw_encrypted = Column(Text, nullable=True)
    message_text_redacted = Column(Text, nullable=True)
    payload_json = Column(JSONB, nullable=True)
    payload_json_encrypted = Column(Text, nullable=True)

    prev_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=True, index=True)

    http_status = Column(Integer, nullable=True)
    provider_error_code = Column(String(100), nullable=True)
    provider_error_message = Column(Text, nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp', 'telegram')", name="ck_channel_message_events_channel"),
        CheckConstraint(
            "direction IN ('inbound', 'outbound', 'status', 'system')",
            name="ck_channel_message_events_direction",
        ),
        CheckConstraint(
            "event_type IN ('webhook_received', 'message_parsed', 'reply_generated', 'send_attempt', "
            "'send_result', 'delivery_status', 'processing_completed', 'exception')",
            name="ck_channel_message_events_event_type",
        ),
        Index(
            "ix_channel_message_events_channel_external_user_occurred",
            "channel",
            "external_user_id",
            "occurred_at",
        ),
        Index("ix_channel_message_events_provider_message_id", "provider_message_id"),
    )


class ChannelDeadLetter(Base):
    __tablename__ = "channel_dead_letters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    trace_id = Column(String(255), nullable=False, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    channel = Column(String(20), nullable=False)
    recipient = Column(String(255), nullable=False)
    payload_json = Column(JSONB, nullable=True)
    error_class = Column(String(255), nullable=False)
    error_message = Column(Text, nullable=False)
    stack_summary = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp', 'telegram')", name="ck_channel_dead_letters_channel"),
    )


class InboundWebhookEnvelope(Base):
    __tablename__ = "inbound_webhook_envelopes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(20), nullable=False, index=True)
    payload_json = Column(JSONB, nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued", index=True)
    enqueued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp', 'telegram')", name="ck_inbound_webhook_envelopes_channel"),
    )


class WebhookIdempotencyKey(Base):
    __tablename__ = "webhook_idempotency_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(20), nullable=False)
    provider_message_id = Column(String(255), nullable=True)
    provider_update_id = Column(String(255), nullable=True)
    idempotency_key = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp', 'telegram')", name="ck_webhook_idempotency_keys_channel"),
        UniqueConstraint("channel", "idempotency_key", name="uq_webhook_idempotency_keys_channel_key"),
        Index("ix_webhook_idempotency_keys_lookup", "channel", "provider_message_id", "provider_update_id"),
    )


class CommitteeMemberLinkCode(Base):
    __tablename__ = "committee_member_link_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    committee_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committee_members.id", ondelete="CASCADE"),
        nullable=False
    )

    code = Column(String(20), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    committee_member = relationship("CommitteeMember", backref="link_codes")


class CommitteeMemberPhoneLinkChallenge(Base):
    __tablename__ = "committee_member_phone_link_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    committee_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committee_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel_type = Column(String(50), nullable=False, index=True)
    external_user_id = Column(String(255), nullable=False, index=True)
    username = Column(String(255), nullable=True)

    phone_number = Column(String(20), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)
    otp_salt = Column(String(64), nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True, index=True)

    attempts_used = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("channel_type IN ('whatsapp', 'telegram')", name="ck_member_phone_challenge_channel"),
    )

    committee_member = relationship("CommitteeMember", backref="phone_link_challenges")
    
    
class Flat(Base):
    __tablename__ = "flats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    society_id = Column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="CASCADE"),
        nullable=False
    )

    flat_number = Column(String(50), nullable=False)
    block = Column(String(50), nullable=False)

    owner_name = Column(String(255), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("society_id", "flat_number", name="uq_flats_society_flat_number"),
        {"schema": None},
    )

    society = relationship("Society", backref="flats")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_society_event_date", "society_id", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    charge_per_adult: Mapped[int | None] = mapped_column(Integer, nullable=True)
    charge_per_child: Mapped[int | None] = mapped_column(Integer, nullable=True)

    food_types: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payment_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # DRAFT / ACTIVE / LOCKED / EVENT_DAY / CLOSED

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    society: Mapped["Society"] = relationship("Society", backref="events")


class EventFoodPass(Base):
    __tablename__ = "event_food_passes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    veg_count: Mapped[int] = mapped_column(Integer, default=0)
    jain_count: Mapped[int] = mapped_column(Integer, default=0)
    kids_count: Mapped[int] = mapped_column(Integer, default=0)

    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_participating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", backref="food_passes")
    flat: Mapped["Flat"] = relationship("Flat")

    __table_args__ = (
        UniqueConstraint("event_id", "flat_id", name="uq_event_food_passes_event_flat"),
    )


class EventFoodToken(Base):
    __tablename__ = "event_food_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)
    flat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False, index=True)

    food_type: Mapped[str] = mapped_column(String(20), nullable=False)
    token_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    qr_payload: Mapped[str] = mapped_column(String(255), nullable=False)

    served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    served_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    served_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", backref="food_tokens")
    flat: Mapped["Flat"] = relationship("Flat")

    __table_args__ = (
        UniqueConstraint("event_id", "token_code", name="uq_event_food_tokens_event_token"),
    )


class EventFoodCounter(Base):
    __tablename__ = "event_food_counters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, unique=True, index=True)

    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", backref="food_counter", uselist=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_event_flat", "event_id", "flat_id"),
        Index("ix_payments_event_paid_at", "event_id", "paid_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    expected_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # pending / partial / paid / refunded
    payment_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", backref="payments")
    flat: Mapped["Flat"] = relationship("Flat")


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        Index("ix_refunds_event_flat", "event_id", "flat_id"),
        Index("ix_refunds_event_created_at", "event_id", "created_at"),
        Index("ix_refunds_event_status", "event_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # requested / approved / refunded / rejected

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    flat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    request_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # requested / approved / rejected

    requested_by_mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_flat_mappings.id"),
        nullable=False,
        index=True
    )
    member_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id"),
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    flat_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    request_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # requested / approved / rejected

    requested_by_mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_flat_mappings.id"),
        nullable=False,
        index=True
    )
    member_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id"),
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventContribution(Base):
    __tablename__ = "event_contributions"
    __table_args__ = (
        Index("ix_event_contributions_event_flat", "event_id", "flat_id"),
        Index("ix_event_contributions_event_created_at", "event_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    contribution_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # example: SP-001

    contribution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)

    flat_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=True)

    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_kind_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    notes: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContributionRefund(Base):
    __tablename__ = "contribution_refunds"
    __table_args__ = (
        Index("ix_contribution_refunds_contribution_processed_at", "contribution_id", "processed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contribution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("event_contributions.id"), nullable=False)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventExpense(Base):
    __tablename__ = "event_expenses"
    __table_args__ = (
        Index("ix_event_expenses_event_created_at", "event_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)

    description = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=False)

    is_override = Column(Boolean, nullable=False, default=False)
    override_reason = Column(String(255))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SocietyBalance(Base):
    __tablename__ = "society_balance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)

    opening_balance = Column(Integer, nullable=False)
    closing_balance = Column(Integer, nullable=False)

    calculated_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkflowState(Base):
    __tablename__ = "workflow_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)

    current_state: Mapped[str] = mapped_column(String(50), nullable=False)
    allowed_next_states: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", backref="workflow_states")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    action = Column(String(50), nullable=False)
    reason = Column(String(255))
    source = Column(String(50), nullable=True)
    trace_id = Column(String(255), nullable=True)
    correlation_id = Column(String(255), nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    old_values_json = Column(JSONB, nullable=True)
    new_values_json = Column(JSONB, nullable=True)

    performed_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    performed_at = Column(DateTime(timezone=True), server_default=func.now())


class MemberIdentity(Base):
    __tablename__ = "member_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_identifier = Column(String, nullable=False, unique=True, index=True)
    normalized_phone = Column(String, nullable=True, index=True)
    whatsapp_user_id = Column(String, nullable=True, unique=True, index=True)
    telegram_user_id = Column(String, nullable=True, unique=True, index=True)
    preferred_language = Column(String(8), nullable=False, default="en")
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserFlatMapping(Base):
    __tablename__ = "user_flat_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    member_identity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id"),
        nullable=False,
        index=True,
    )

    role = Column(String, default="member")  
    # member / owner / tenant (future-proof)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    
class ReminderConfig(Base):
    __tablename__ = "reminder_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    society_id = Column(
        UUID(as_uuid=True),
        ForeignKey("societies.id"),
        nullable=False,
        unique=True
    )

    enabled = Column(Boolean, default=True)

    # time in 24h format
    run_hour = Column(Integer, nullable=False)    # 0–23
    run_minute = Column(Integer, nullable=False)  # 0–59

    frequency = Column(String, default="daily")
    # daily / weekly (future)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentReminder(Base):
    __tablename__ = "payment_reminders"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "flat_id",
            "reminder_date",
            name="uq_payment_reminders_event_flat_date",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    pending_amount = Column(Integer, nullable=False)

    reminder_date = Column(Date, nullable=False)
    status = Column(String, default="generated")  
    # generated / sent / skipped

    created_at = Column(DateTime(timezone=True), server_default=func.now())
        
    
class PendingUser(Base):
    __tablename__ = "pending_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

    request_code = Column(String, nullable=False, index=True)
    # e.g. REQ-001

    member_identity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id"),
        nullable=False,
        index=True,
    )
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    status = Column(String, default="pending")
    # pending / approved / rejected

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)

    type = Column(String(50), nullable=False)
    message_text = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"), nullable=False)

    status = Column(String(50), nullable=False, default="queued")
    total_targets = Column(Integer, nullable=False, default=0)
    sent_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    society = relationship("Society", backref="announcements")
    event = relationship("Event", backref="announcements")


class AnnouncementDelivery(Base):
    __tablename__ = "announcement_deliveries"
    __table_args__ = (
        Index(
            "idx_announcement_deliveries_claim_pending",
            "status",
            "processing_started_at",
            "sent_at",
            "announcement_id",
        ),
    )

    announcement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    member_identity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    channel = Column(String(50), primary_key=True)

    recipient_id = Column(String(255), nullable=False)
    rendered_payload = Column(JSONB, nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)

    announcement = relationship("Announcement", backref="deliveries")
    member_identity = relationship("MemberIdentity", backref="announcement_deliveries")
