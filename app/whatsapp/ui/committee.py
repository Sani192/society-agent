from __future__ import annotations


def build_committee_sections() -> list[dict]:
    # WhatsApp interactive list messages support at most 10 rows in total.
    return [
        {
            "title": "Approvals",
            "rows": [
                {"id": "pending payments", "title": "Pending Payments", "description": "Members with outstanding dues"},
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
            "title": "More",
            "rows": [
                {"id": "ui::administration:more", "title": "More Actions", "description": "Templates and reports"},
            ],
        },
    ]


def build_committee_more_sections() -> list[dict]:
    return [
        {
            "title": "Approval Templates",
            "rows": [
                {"id": "ui::approve-user", "title": "Approve User", "description": "Template: approve user REQ-001"},
                {
                    "id": "ui::approve-payment",
                    "title": "Approve Payment",
                    "description": "Template: approve payment PAY-001",
                },
                {
                    "id": "ui::approve-refund",
                    "title": "Approve Refund",
                    "description": "Template: approve refund REF-001",
                },
            ],
        },
        {
            "title": "Reports",
            "rows": [
                {"id": "report options", "title": "Report Options", "description": "Export financial reports"},
                {"id": "participation report", "title": "Participation Report", "description": "Member analytics"},
            ],
        },
    ]
