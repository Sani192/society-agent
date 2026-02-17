from __future__ import annotations


def build_committee_sections() -> list[dict]:
    return [
        {
            "title": "Approvals",
            "rows": [
                {"id": "payment requests", "title": "Payment Requests", "description": "Approve payment entries"},
                {"id": "refund requests", "title": "Refund Requests", "description": "Approve refund entries"},
                {"id": "pending users", "title": "Pending Users", "description": "Review join approvals"},
                {
                    "id": "ui::approve-user",
                    "title": "Guided User Approval",
                    "description": "Get approve user command template",
                },
                {
                    "id": "ui::approve-payment",
                    "title": "Guided Payment Approval",
                    "description": "Get approve payment command template",
                },
                {
                    "id": "ui::approve-refund",
                    "title": "Guided Refund Approval",
                    "description": "Get approve refund command template",
                },
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
                {"id": "pending payments", "title": "Pending Payments", "description": "List unpaid flats"},
                {"id": "block report", "title": "Block Report", "description": "Block-wise contribution report"},
                {"id": "summary", "title": "Audit Reports", "description": "Governance summaries"},
            ],
        },
    ]
