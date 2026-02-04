from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


@dataclass
class QueryMock:
    first_result: object = None
    scalar_result: object = None
    all_result: object = None
    count_result: object = None

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_result

    def scalar(self):
        return self.scalar_result

    def all(self):
        return self.all_result

    def count(self):
        return self.count_result


@pytest.fixture
def db_session():
    return MagicMock()
