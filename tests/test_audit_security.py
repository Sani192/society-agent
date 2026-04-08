import base64
import hashlib
import hmac
from datetime import datetime, timezone

from app.channels.core import audit_events
from app.channels.core.audit_events import NormalizedAuditEvent, persist_audit_events
from app.channels.core.audit_security import decrypt_from_audit_store
from app.config import settings


def test_encrypted_raw_pii_mode_stores_ciphertext_and_redacted_payload(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_PII_CAPTURE_MODE", "encrypted_raw")
    monkeypatch.setattr(settings, "AUDIT_ENCRYPTION_KEY", "unit-test-key")

    event = NormalizedAuditEvent(
        channel="whatsapp",
        direction="inbound",
        event_type="message_parsed",
        message_text_raw="my phone is 9999991234",
        payload_json={"token": "secret-token", "safe": "ok"},
        occurred_at=datetime.now(timezone.utc),
    )

    row = event.to_db_model()

    assert row.message_text_raw == "[REDACTED]"
    assert row.payload_json == {"token": "[REDACTED]", "safe": "ok"}
    assert row.message_text_raw_encrypted
    assert row.message_text_raw_encrypted.startswith("v2:")
    assert row.payload_json_encrypted
    assert decrypt_from_audit_store(row.message_text_raw_encrypted) == "my phone is 9999991234"


def test_decrypt_from_audit_store_supports_legacy_ciphertext(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_ENCRYPTION_KEY", "unit-test-key")

    key = hashlib.sha256("unit-test-key".encode("utf-8")).digest()
    nonce = b"0123456789abcdef"
    plaintext = b"legacy-payload"
    stream = bytearray()
    counter = 0
    while len(stream) < len(plaintext):
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream[: len(plaintext)]))
    signature = hmac.new(key, nonce + ciphertext, digestmod=hashlib.sha256).digest()
    legacy_blob = base64.urlsafe_b64encode(nonce + signature + ciphertext).decode("utf-8")

    assert decrypt_from_audit_store(legacy_blob) == "legacy-payload"


def test_persist_audit_events_builds_hash_chain(monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_PII_CAPTURE_MODE", "redacted")

    stored = []

    class QueryStub:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class SessionStub:
        def query(self, *args, **kwargs):
            return QueryStub()

        def add(self, row):
            stored.append(row)

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(audit_events, "SessionLocal", lambda: SessionStub())

    first = NormalizedAuditEvent(
        channel="telegram",
        direction="system",
        event_type="processing_completed",
        payload_json={"n": 1},
        occurred_at=datetime.now(timezone.utc),
    )
    second = NormalizedAuditEvent(
        channel="telegram",
        direction="system",
        event_type="processing_completed",
        payload_json={"n": 2},
        occurred_at=datetime.now(timezone.utc),
    )

    assert persist_audit_events([first, second]) == 2
    assert len(stored) == 2
    assert stored[0].event_hash
    assert stored[1].prev_event_hash == stored[0].event_hash
    assert stored[1].event_hash
