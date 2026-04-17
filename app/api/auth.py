from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.utils.security_logging import log_security_event
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _raise_invalid_token(detail: str, *, reason_code: str, actor_id: str | None = None) -> None:
    log_security_event(
        logger,
        event="invalid_token_check",
        actor_id=actor_id,
        action="verify_reports_api_token",
        resource_id="reports_api_auth",
        method="bearer_token",
        result="denied",
        reason_code=reason_code,
    )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    committee_member_id: uuid.UUID | None = None
    channel_type: str | None = None
    external_user_id: str | None = None
    phone: str | None = None


_http_bearer = HTTPBearer(auto_error=False)


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _verify_and_decode_principal_token(token: str) -> dict:
    signing_secret = getattr(settings, "REPORTS_API_AUTH_SECRET", None)
    if not signing_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report API authentication is not configured",
        )

    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError:
        _raise_invalid_token("Invalid auth token", reason_code="TOKEN_MALFORMED")

    expected_signature = hmac.new(
        signing_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    provided_signature = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected_signature, provided_signature):
        _raise_invalid_token("Invalid auth token signature", reason_code="TOKEN_SIGNATURE_INVALID")

    try:
        payload_json = _b64url_decode(payload_part)
        payload = json.loads(payload_json.decode("utf-8"))
    except Exception:
        _raise_invalid_token("Invalid auth token payload", reason_code="TOKEN_PAYLOAD_DECODE_INVALID")

    if not isinstance(payload, dict):
        _raise_invalid_token("Invalid auth token payload", reason_code="TOKEN_PAYLOAD_TYPE_INVALID")

    now_ts = int(datetime.now(timezone.utc).timestamp())

    exp = payload.get("exp")
    if exp is None:
        _raise_invalid_token("Auth token missing expiry", reason_code="TOKEN_EXP_MISSING")

    try:
        exp_ts = int(exp)
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        _raise_invalid_token("Invalid auth token expiry", reason_code="TOKEN_EXP_INVALID")
    if exp_dt <= datetime.now(timezone.utc):
        _raise_invalid_token("Auth token expired", reason_code="TOKEN_EXPIRED")

    iat = payload.get("iat")
    if iat is None:
        _raise_invalid_token("Auth token missing issued-at", reason_code="TOKEN_IAT_MISSING")
    try:
        iat_ts = int(iat)
        datetime.fromtimestamp(iat_ts, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        _raise_invalid_token("Invalid auth token issued-at", reason_code="TOKEN_IAT_INVALID")

    max_iat_future_skew = max(
        0,
        int(getattr(settings, "REPORTS_API_AUTH_MAX_IAT_FUTURE_SKEW_SECONDS", 300)),
    )
    if iat_ts > (now_ts + max_iat_future_skew):
        _raise_invalid_token("Auth token issued-at is in the future", reason_code="TOKEN_IAT_IN_FUTURE")

    max_ttl_seconds = max(1, int(getattr(settings, "REPORTS_API_AUTH_MAX_TTL_SECONDS", 3600)))
    if exp_ts - iat_ts > max_ttl_seconds:
        _raise_invalid_token("Auth token expiry exceeds max TTL", reason_code="TOKEN_TTL_EXCEEDED")

    expected_aud = getattr(settings, "REPORTS_API_AUTH_AUDIENCE", None)
    if expected_aud and payload.get("aud") != expected_aud:
        _raise_invalid_token("Invalid auth token audience", reason_code="TOKEN_AUDIENCE_INVALID")

    return payload


def get_authenticated_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> AuthenticatedPrincipal:
    if credentials is None or not credentials.credentials:
        _raise_invalid_token("Missing bearer token", reason_code="TOKEN_MISSING")

    payload = _verify_and_decode_principal_token(credentials.credentials)
    member_id_raw = payload.get("committee_member_id")
    channel_type = payload.get("channel_type")
    external_user_id = payload.get("external_user_id")
    phone = payload.get("phone")

    committee_member_id = None
    if member_id_raw is not None:
        try:
            committee_member_id = uuid.UUID(str(member_id_raw))
        except (TypeError, ValueError):
            _raise_invalid_token("Invalid committee member id", reason_code="TOKEN_MEMBER_ID_INVALID")

    if committee_member_id is None and not (channel_type and external_user_id):
        _raise_invalid_token(
            "Auth token must include committee member id or channel identity",
            reason_code="TOKEN_PRINCIPAL_MISSING",
        )

    return AuthenticatedPrincipal(
        committee_member_id=committee_member_id,
        channel_type=str(channel_type) if channel_type else None,
        external_user_id=str(external_user_id) if external_user_id else None,
        phone=str(phone) if phone else None,
    )


def build_reports_auth_token(
    *,
    payload: dict,
    signing_secret: str,
    ttl_seconds: int = 900,
    audience: str | None = None,
    include_standard_claims: bool = True,
) -> str:
    """Test/helper utility for generating backend-signed report auth tokens."""
    normalized_payload = dict(payload)
    if include_standard_claims:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        normalized_payload.setdefault("iat", now_ts)
        normalized_payload.setdefault("exp", now_ts + ttl_seconds)
        if audience is not None:
            normalized_payload.setdefault("aud", audience)
    payload_encoded = _b64url_encode(json.dumps(normalized_payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        payload_encoded.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{payload_encoded}.{_b64url_encode(signature)}"
