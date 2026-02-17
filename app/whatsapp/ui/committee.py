from __future__ import annotations


def build_committee_sections() -> list[dict]:
    # WhatsApp interactive list messages support at most 10 rows in total.
    # Keep high-frequency administrative actions here and rely on text commands
    # for less common flows.
    return [
        {
            "title": "Approvals",
            "rows": [
                {"id": "payment requests", "title": "Payment Requests", "description": "Approve payment entries"},
                {"id": "refund requests", "title": "Refund Requests", "description": "Approve refund entries"},
                {"id": "pending users", "title": "Pending Users", "description": "Review join approvals"},
            ],
        },
        {
            "title": "Operations",
            "rows": [
                {"id": "add event", "title": "Add Event", "description": "Create a new event"},
                {"id": "expense", "title": "Add Expense", "description": "Record event expense"},
                {"id": "add sponsor", "title": "Add Sponsor", "description": "Record sponsor contribution"},
                {"id": "refund sponsor", "title": "Refund Sponsor", "description": "Reverse sponsor entry"},
                {"id": "remind", "title": "Remind Flat", "description": "Send payment reminder"},
            ],
        },
        {
            "title": "Reports",
            "rows": [
                {"id": "report options", "title": "Financial Reports", "description": "Export financial reports"},
                {"id": "participation report", "title": "Member Reports", "description": "Participation analytics"},
            ],
        },
    ]
