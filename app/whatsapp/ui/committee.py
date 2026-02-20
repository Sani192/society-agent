from __future__ import annotations


def build_committee_sections() -> list[dict]:
    # WhatsApp interactive list messages support at most 10 rows in total.
    return [
        {
            "title": "Approvals",
            "rows": [
                {"id": "pending users", "title": "Pending Users", "description": "Review join approvals"},
                {"id": "payment requests", "title": "Payment Requests", "description": "Approve payment entries"},
                {"id": "refund requests", "title": "Refund Requests", "description": "Approve refund entries"},
                {"id": "ui::approve-user", "title": "Approve User", "description": "Send: approve user <request_code>"},
            ],
        },
        {
            "title": "Operations",
            "rows": [
                {"id": "add event", "title": "Add Event", "description": "Guided setup for a new event"},
                {"id": "expense", "title": "Add Expense", "description": "Record event expense"},
                {"id": "add sponsor", "title": "Add Sponsor", "description": "Record sponsor contribution"},
                {"id": "remind", "title": "Remind Flat", "description": "Send payment reminder"},
            ],
        },
        {
            "title": "Reports & Templates",
            "rows": [
                {"id": "report options", "title": "Report Options", "description": "Export financial reports"},
                {"id": "ui::approve-payment", "title": "Approve Payment", "description": "Send: approve payment <request_code>"},
            ],
        },
    ]


def build_committee_more_sections() -> list[dict]:
    return [
        {
            "title": "Approval Templates",
            "rows": [
                {"id": "ui::approve-user", "title": "Approve User", "description": "Send: approve user <request_code>"},
                {
                    "id": "ui::approve-payment",
                    "title": "Approve Payment",
                    "description": "Send: approve payment <request_code>",
                },
                {
                    "id": "ui::approve-refund",
                    "title": "Approve Refund",
                    "description": "Send: approve refund <request_code>",
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
