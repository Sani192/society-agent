from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.users.language_service import DEFAULT_LANGUAGE, resolve_sender_language


def _mock_db_with_language(language: str | None):
    db = MagicMock()
    identity = SimpleNamespace(preferred_language=language) if language is not None else None
    db.query.return_value.filter.return_value.first.return_value = identity
    return db


def test_resolve_sender_language_returns_whatsapp_identity_preference():
    db = _mock_db_with_language("hi")

    lang = resolve_sender_language(
        db,
        sender_id="+91 99990 00001",
        channel="whatsapp",
    )

    assert lang == "hi"


def test_resolve_sender_language_returns_default_when_sender_missing():
    db = _mock_db_with_language("gu")

    lang = resolve_sender_language(
        db,
        sender_id=None,
        channel="whatsapp",
    )

    assert lang == DEFAULT_LANGUAGE


def test_resolve_sender_language_returns_default_when_db_lookup_errors():
    db = MagicMock()
    db.query.side_effect = RuntimeError("db unavailable")

    lang = resolve_sender_language(
        db,
        sender_id="919999000001",
        channel="telegram",
    )

    assert lang == DEFAULT_LANGUAGE
