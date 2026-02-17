from __future__ import annotations


def build_committee_sections() -> list[dict]:
    return [
        {
            "title": "Approvals",
            "rows": [
                {"id": "payment requests", "title": "Payment Requests", "description": "Approve payment entries"},
                {"id": "refund requests", "title": "Refund Requests", "description": "Approve refund entries"},
            ],
        },
        {
            "title": "Operations",
            "rows": [
                {"id": "expense", "title": "Add Expense", "description": "Record event expense"},
                {"id": "add sponsor", "title": "Add Sponsor", "description": "Record sponsor contribution"},
                {"id": "refund sponsor", "title": "Refund Sponsor", "description": "Reverse sponsor entry"},
            ],
        },
        {
            "title": "Reports",
            "rows": [
                {"id": "report options", "title": "Financial Reports", "description": "Export financial reports"},
                {"id": "participation report", "title": "Member Reports", "description": "Participation analytics"},
                {"id": "summary", "title": "Audit Reports", "description": "Governance summaries"},
            ],
        },
    ]
