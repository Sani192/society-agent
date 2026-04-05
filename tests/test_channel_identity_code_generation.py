import random
import string
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.users.channel_identity_service import (
    LINK_CODE_LENGTH,
    _generate_code,
    create_member_link_code,
)


def test_generate_code_has_expected_charset_and_length():
    code = _generate_code()

    assert len(code) == LINK_CODE_LENGTH
    assert set(code) <= set(string.ascii_uppercase + string.digits)


def test_generate_code_does_not_depend_on_random_module(monkeypatch):
    def _raise_if_used(*args, **kwargs):
        raise AssertionError("random.choice should not be used")

    monkeypatch.setattr(random, "choice", _raise_if_used)

    code = _generate_code()

    assert len(code) == LINK_CODE_LENGTH


def test_create_member_link_code_retries_until_unique(monkeypatch):
    db = MagicMock()
    member = SimpleNamespace(id=uuid4())

    generated_codes = iter(["AAAAAA", "BBBBBB"])
    monkeypatch.setattr(
        "app.modules.users.channel_identity_service._generate_code",
        lambda: next(generated_codes),
    )

    db.query.return_value.filter.return_value.first.side_effect = [object(), None]

    link_code = create_member_link_code(db=db, member=member)

    assert link_code.code == "BBBBBB"
    assert db.query.return_value.filter.return_value.first.call_count == 2
    db.add.assert_called_once_with(link_code)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(link_code)
