#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:28:42 2026

@author: anonymous
"""

# app/utils/guards.py

from app.config import settings
from app.db.models import CommitteeMember
from app.modules.users.channel_identity_service import resolve_committee_member_by_identity
from app.db.session import SessionLocal
from app.modules.users.user_flat_service import UserFlatService
import re

def normalize_phone(phone: str) -> str | None:
    if not phone:
        return None

    # keep digits only
    digits = re.sub(r"\D", "", phone)

    # handle India country code
    # if digits.startswith("91") and len(digits) == 12:
    #    digits = digits[2:]

    # final validation
    # if len(digits) != 10:
    #    return None

    return digits


def ensure_admin(phone_number: str):
    normalized = normalize_phone(phone_number)
    whitelist = [normalize_phone(p) for p in settings.ADMIN_PHONE_WHITELIST]

    if normalized not in whitelist:
        raise Exception("You are not allowed to perform this action")


def ensure_reason(reason: str):
    if not reason or len(reason.strip()) < 5:
        raise Exception("Override reason must be at least 5 characters")
        
def ensure_member_of_society(
    phone_number: str,
    db: SessionLocal,
    society_id
):
    normalized = normalize_phone(phone_number)
    if not normalized:
        raise Exception("Invalid phone number")
        
    mappings = UserFlatService.get_flats_for_user(
        db=db,
        society_id=society_id,
        user_identifier=normalized
    )
    
    if not mappings:
        raise Exception("Your flat is not registered. Please contact admin.")
    
    return mappings


def ensure_committee_member(
    phone_number: str,
    db: SessionLocal,
    *,
    channel_type: str = "whatsapp",
    external_user_id: str | None = None,
    username: str | None = None,
) -> CommitteeMember:
    sender_id = external_user_id or phone_number
    member = resolve_committee_member_by_identity(
        db=db,
        channel_type=channel_type,
        sender_id=sender_id,
        phone_number=phone_number,
        username=username,
    )

    if not member or not member.is_active:
        raise Exception("You are not authorized.")

    return member

