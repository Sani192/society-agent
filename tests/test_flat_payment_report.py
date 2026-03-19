from app.modules.reports.financial.flat_payment_report import FlatPaymentReport
from tests.utils import QueryMock


class FlatPaymentReportQueryMock(QueryMock):
    def outerjoin(self, *args, **kwargs):
        return self


def test_flat_payment_report_headers_and_rows(db_session):
    db_session.query.return_value = FlatPaymentReportQueryMock(
        all_result=[
            ("A-101", "A", 500, 300, 0, None, None),
            ("B-202", "B", 0, 0, 0, None, None),
        ]
    )

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
