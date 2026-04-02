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
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from exc

    expected_signature = hmac.new(
        signing_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    provided_signature = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token signature")

    try:
        payload_json = _b64url_decode(payload_part)
        payload = json.loads(payload_json.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token payload") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token payload")

    exp = payload.get("exp")
    if exp is not None:
        try:
            exp_dt = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        except (TypeError, ValueError, OSError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token expiry") from exc
        if exp_dt <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth token expired")

    return payload


def get_authenticated_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> AuthenticatedPrincipal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = _verify_and_decode_principal_token(credentials.credentials)
    member_id_raw = payload.get("committee_member_id")
    channel_type = payload.get("channel_type")
    external_user_id = payload.get("external_user_id")
    phone = payload.get("phone")

    committee_member_id = None
    if member_id_raw is not None:
        try:
            committee_member_id = uuid.UUID(str(member_id_raw))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid committee member id") from exc

    if committee_member_id is None and not (channel_type and external_user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth token must include committee member id or channel identity",
        )

    return AuthenticatedPrincipal(
        committee_member_id=committee_member_id,
        channel_type=str(channel_type) if channel_type else None,
        external_user_id=str(external_user_id) if external_user_id else None,
        phone=str(phone) if phone else None,
    )


def build_reports_auth_token(*, payload: dict, signing_secret: str) -> str:
    """Test/helper utility for generating backend-signed report auth tokens."""
    payload_encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        payload_encoded.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{payload_encoded}.{_b64url_encode(signature)}"
