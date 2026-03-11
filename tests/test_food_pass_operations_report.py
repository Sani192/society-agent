from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.reports.operations.food_pass_report import FoodPassOperationsReport
from tests.utils import QueryMock


def test_food_pass_operations_report_mixed_token_and_fallback_serving(monkeypatch):
    passes = [
        SimpleNamespace(flat_id="flat-1", veg_count=2, jain_count=1, kids_count=0),
        SimpleNamespace(flat_id="flat-2", veg_count=1, jain_count=0, kids_count=1),
    ]
    token_flat_ids = [("flat-1",), ("flat-2",)]
    flat_rows = [
        ("flat-1", "A-101", "A"),
        ("flat-2", "B-202", "B"),
    ]

    monkeypatch.setattr(
        "app.modules.reports.operations.food_pass_report.FoodCollectionService.dashboard",
        lambda **kwargs: {
            "served_plates": 4,
            "by_type": {
                "veg": {"total": 3, "served": 2, "remaining": 1},
                "jain": {"total": 1, "served": 1, "remaining": 0},
                "kids": {"total": 1, "served": 0, "remaining": 1},
                "fallback": {"total": 1, "served": 1, "remaining": 0},
            },
        },
    )

    statuses = {
        "flat-1": {"served": 3, "fallback_served": 1},
        "flat-2": {"served": 1, "fallback_served": 0},
    }

    monkeypatch.setattr(
        "app.modules.reports.operations.food_pass_report.FoodCollectionService.member_pass_status",
        lambda **kwargs: statuses[kwargs["flat_id"]],
    )

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(all_result=passes),
        QueryMock(all_result=token_flat_ids),
        QueryMock(all_result=flat_rows),
    ]

    report = FoodPassOperationsReport.generate(db=db, event_id="event-1")

    assert report["summary"]["total_passes_generated"] == 5
    assert report["summary"]["fallback_serve_count"] == 1
    assert report["summary"]["served_count"] == 4
    assert report["summary"]["remaining_count"] == 1

    assert report["summary"]["by_food_type"] == {
        "jain": {"total": 1, "served": 1, "remaining": 0},
        "kids": {"total": 1, "served": 0, "remaining": 1},
        "veg": {"total": 3, "served": 2, "remaining": 1},
    }

    assert report["rows"] == [
        ["A-101", "A", 3, 2, 1, 3, 0],
        ["B-202", "B", 2, 1, 0, 1, 1],
    ]
