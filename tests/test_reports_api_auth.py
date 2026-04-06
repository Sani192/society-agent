from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.auth import (
    build_reports_auth_token,
    get_authenticated_principal,
)


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_rejects_phone_only_token(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    token = build_reports_auth_token(payload={"phone": "919999000000"}, signing_secret="reports-secret")

    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_principal(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    assert exc_info.value.status_code == 401
    assert "committee member id or channel identity" in str(exc_info.value.detail)


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_uses_signed_principal_not_phone_query(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    token = build_reports_auth_token(
        payload={
            "committee_member_id": str(uuid4()),
            "phone": "attacker-spoofed-phone",
        },
        signing_secret="reports-secret",
    )

    principal = get_authenticated_principal(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert principal.committee_member_id is not None
    assert principal.phone == "attacker-spoofed-phone"


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_rejects_token_missing_exp(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    token = build_reports_auth_token(
        payload={
            "committee_member_id": str(uuid4()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        },
        signing_secret="reports-secret",
        include_standard_claims=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_principal(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    assert exc_info.value.status_code == 401
    assert "missing expiry" in str(exc_info.value.detail)


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_rejects_expired_token(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = build_reports_auth_token(
        payload={
            "committee_member_id": str(uuid4()),
            "iat": now_ts - 120,
            "exp": now_ts - 60,
        },
        signing_secret="reports-secret",
        include_standard_claims=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_principal(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    assert exc_info.value.status_code == 401
    assert "expired" in str(exc_info.value.detail)


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_rejects_missing_iat(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    token = build_reports_auth_token(
        payload={
            "committee_member_id": str(uuid4()),
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
        },
        signing_secret="reports-secret",
        include_standard_claims=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_principal(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    assert exc_info.value.status_code == 401
    assert "missing issued-at" in str(exc_info.value.detail)


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_rejects_ttl_exceeding_max_window(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_MAX_TTL_SECONDS", 900)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = build_reports_auth_token(
        payload={
            "committee_member_id": str(uuid4()),
            "iat": now_ts,
            "exp": now_ts + 3600,
        },
        signing_secret="reports-secret",
        include_standard_claims=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_principal(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    assert exc_info.value.status_code == 401
    assert "max TTL" in str(exc_info.value.detail)


@pytest.mark.integration
@pytest.mark.endpoint
def test_reports_auth_rejects_invalid_audience_when_configured(monkeypatch):
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_SECRET", "reports-secret")
    monkeypatch.setattr("app.api.auth.settings.REPORTS_API_AUTH_AUDIENCE", "reports-api")
    token = build_reports_auth_token(
        payload={
            "committee_member_id": str(uuid4()),
        },
        signing_secret="reports-secret",
        audience="wrong-aud",
    )

    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_principal(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

    assert exc_info.value.status_code == 401
    assert "audience" in str(exc_info.value.detail)
