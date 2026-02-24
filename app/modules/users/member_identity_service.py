#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from sqlalchemy.orm import Session

from app.db.models import MemberIdentity
from app.utils.identity import normalize_identifier
from app.utils.logging_helpers import log_service_call

logger = logging.getLogger(__name__)


class MemberIdentityService:

    @staticmethod
    @log_service_call(logger, "MemberIdentityService.resolve_or_create")
    def resolve_or_create(db: Session, *, user_identifier: str) -> MemberIdentity:
        normalized_identifier = normalize_identifier(user_identifier)
        if not normalized_identifier:
            raise Exception("Invalid user identifier")

        identity = (
            db.query(MemberIdentity)
            .filter(MemberIdentity.normalized_identifier == normalized_identifier)
            .first()
        )
        if identity:
            return identity

        identity = MemberIdentity(
            normalized_identifier=normalized_identifier,
            normalized_phone=normalized_identifier,
            metadata_json={"source": "resolved"},
        )
        db.add(identity)
        db.flush()
        return identity
