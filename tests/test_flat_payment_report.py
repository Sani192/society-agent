from types import SimpleNamespace

from app.modules.reports.financial.flat_payment_report import FlatPaymentReport
from tests.utils import QueryMock


def test_flat_payment_report_headers_and_rows(db_session):
    flat_one = SimpleNamespace(id="flat-1", flat_number="A-101", block="A")
    flat_two = SimpleNamespace(id="flat-2", flat_number="B-202", block="B")
    payment = SimpleNamespace(paid_amount=300, expected_amount=500)

    db_session.query.side_effect = [
        QueryMock(all_result=[flat_one, flat_two]),
        QueryMock(first_result=payment),
        QueryMock(first_result=None),
    ]

    report = FlatPaymentReport.generate(db_session, event_id="event-1")

    assert report["headers"] == ["Flat", "Block", "Expected", "Paid", "Pending"]
    assert report["rows"] == [
        ["A-101", "A", 500, 300, 200],
        ["B-202", "B", 0, 0, 0],
    ]
