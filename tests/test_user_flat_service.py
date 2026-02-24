from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.users.user_flat_service import UserFlatService
from tests.utils import QueryMock


def test_assign_user_to_flat_handles_unique_violation_cleanly():
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=SimpleNamespace(id="identity-1", normalized_identifier="919999000001")),
        QueryMock(first_result=None),
    ]
    db.flush.return_value = None
    db.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate key"))

    with pytest.raises(Exception, match="You are already registered with this society."):
        UserFlatService.assign_user_to_flat(
            db=db,
            society_id="soc-1",
            flat_id="flat-1",
            member_identity_id="identity-1",
            performed_by=None,
        )

    db.rollback.assert_called_once()
