from app.modules.reports.financial.flat_payment_report import FlatPaymentReport
from tests.utils import QueryMock


def test_flat_payment_report_headers_and_rows(db_session):
    query = QueryMock(
        all_result=[
            ("A-101", "A", 500, 300, 0, None, None),
            ("B-202", "B", 0, 0, 0, None, None),
        ]
    )
    db_session.query.return_value = query

    report = FlatPaymentReport.generate(db_session, event_id="event-1")

    assert report["headers"] == [
        "Flat",
        "Block",
        "Expected",
        "Paid",
        "Refunded",
        "Pending",
        "Created At",
        "Created By",
        "Updated At",
        "Updated By"
    ]
    assert report["rows"] == [
        ["A-101", "A", 500, 300, 0, 200, "-", "System", "-", "System"],
        ["B-202", "B", 0, 0, 0, 0, "-", "System", "-", "System"],
    ]
