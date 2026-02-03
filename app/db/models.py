#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:22:14 2026

@author: anonymous
"""

# app/db/models.py

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Date
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
        # One flat number must be unique within a society
        {"schema": None},
    )

    society = relationship("Society", backref="flats")


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

    name = Column(String(255), nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)

    charge_per_person = Column(Integer, nullable=True)

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


class EventContribution(Base):
    __tablename__ = "event_contributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)

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


class UserFlatMapping(Base):
    __tablename__ = "user_flat_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    # External user identity (platform-agnostic)
    # WhatsApp: phone number
    # Telegram: user_id
    # Web: user_id
    user_identifier = Column(String, nullable=False, index=True)

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

    user_identifier = Column(String, nullable=False, index=True)
    flat_number = Column(String, nullable=False)

    status = Column(String, default="pending")
    # pending / approved / rejected

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    

class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)

    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id"), nullable=False)

    requested_by = Column(UUID(as_uuid=True), ForeignKey("user_flat_mappings.id"), nullable=False)

    amount = Column(Integer, nullable=False)

    status = Column(String, default="pending")
    # pending / approved / rejected

    created_at = Column(DateTime(timezone=True), server_default=func.now())

