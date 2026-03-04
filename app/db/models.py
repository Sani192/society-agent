#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:22:14 2026

@author: anonymous
"""

# app/db/models.py

import uuid
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
from sqlalchemy.orm import relationship

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
        # chairman | secretary | treasurer
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

    name = Column(String(255), nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)

    charge_per_adult = Column(Integer, nullable=True)
    charge_per_child = Column(Integer, nullable=True)

    food_types = Column(JSONB, nullable=False)
    payment_deadline = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), nullable=False)  # DRAFT / ACTIVE / LOCKED / EVENT_DAY / CLOSED

    created_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    society = relationship("Society", backref="events")


class EventFoodPass(Base):
    __tablename__ = "event_food_passes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    veg_count = Column(Integer, default=0)
    jain_count = Column(Integer, default=0)
    kids_count = Column(Integer, default=0)

    total_amount = Column(Integer, nullable=False)
    is_participating = Column(Boolean, nullable=False, default=True)
    is_locked = Column(Boolean, nullable=False, default=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    expected_amount = Column(Integer, nullable=False)
    paid_amount = Column(Integer, nullable=False, default=0)

    status = Column(String(50), nullable=False)  # pending / partial / paid / refunded
    payment_mode = Column(String(50), nullable=True)

    paid_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    amount = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)

    status = Column(String(50), nullable=False)  # requested / approved / refunded / rejected

    created_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    request_code = Column(String(50), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    payment_mode = Column(String(50), nullable=True)

    status = Column(String(50), nullable=False)  # requested / approved / rejected

    requested_by_mapping_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_flat_mappings.id"),
        nullable=False,
        index=True
    )
    member_identity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id"),
        nullable=False,
        index=True,
    )
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    approved_at = Column(DateTime(timezone=True))


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    request_code = Column(String(50), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)

    status = Column(String(50), nullable=False)  # requested / approved / rejected

    requested_by_mapping_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_flat_mappings.id"),
        nullable=False,
        index=True
    )
    member_identity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("member_identities.id"),
        nullable=False,
        index=True,
    )
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    approved_at = Column(DateTime(timezone=True))


class EventContribution(Base):
    __tablename__ = "event_contributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    contribution_code = Column(String(20), nullable=False, index=True)
    # example: SP-001

    contribution_type = Column(String(50), nullable=False)
    source_name = Column(String(255), nullable=False)

    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=True)

    amount = Column(Integer, nullable=True)
    in_kind_details = Column(JSONB, nullable=True)

    notes = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContributionRefund(Base):
    __tablename__ = "contribution_refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contribution_id = Column(UUID(as_uuid=True), ForeignKey("event_contributions.id"), nullable=False)

    amount = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)

    processed_at = Column(DateTime(timezone=True))


class EventExpense(Base):
    __tablename__ = "event_expenses"

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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)

    current_state = Column(String(50), nullable=False)
    allowed_next_states = Column(JSONB, nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    action = Column(String(50), nullable=False)
    reason = Column(String(255))

    performed_by = Column(UUID(as_uuid=True), ForeignKey("committee_members.id"))
    performed_at = Column(DateTime(timezone=True), server_default=func.now())


class MemberIdentity(Base):
    __tablename__ = "member_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_identifier = Column(String, nullable=False, unique=True, index=True)
    normalized_phone = Column(String, nullable=True, index=True)
    whatsapp_user_id = Column(String, nullable=True, unique=True, index=True)
    telegram_user_id = Column(String, nullable=True, unique=True, index=True)
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

    announcement = relationship("Announcement", backref="deliveries")
    member_identity = relationship("MemberIdentity", backref="announcement_deliveries")
