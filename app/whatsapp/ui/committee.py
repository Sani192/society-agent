from __future__ import annotations


def build_committee_sections() -> list[dict]:
    return [
        {
            "title": "Administration",
            "rows": [
                {"id": "ui::administration:approvals", "title": "Approvals", "description": "Review users, payments, and refunds"},
                {"id": "ui::administration:operations", "title": "Operations", "description": "Manage event and finance operations"},
                {"id": "ui::administration:reports", "title": "Reports", "description": "Open committee report actions"},
            ],
        }
    ]


def build_committee_approvals_sections() -> list[dict]:
    return [
        {
            "title": "Approvals",
            "rows": [
                {"id": "pending users", "title": "Pending Users", "description": "Review join approvals"},
                {"id": "payment requests", "title": "Payment Requests", "description": "Approve payment entries"},
                {"id": "refund requests", "title": "Refund Requests", "description": "Approve refund entries"},
                {"id": "pending payments", "title": "Pending Payments", "description": "Members with outstanding dues"},
                {"id": "ui::approve-user", "title": "Approve User", "description": "Send: approve user <request_code>"},
                {"id": "ui::approve-payment", "title": "Approve Payment", "description": "Send: approve payment <request_code>"},
                {"id": "ui::approve-refund", "title": "Approve Refund", "description": "Send: approve refund <request_code>"},
            ],
        }
    ]


def build_committee_operations_sections() -> list[dict]:
    return [
        {
            "title": "Event Lifecycle",
            "rows": [
                {"id": "add event", "title": "Add Event", "description": "Guided setup for a new event"},
                {"id": "activate event", "title": "Activate Event", "description": "Move event to active"},
                {"id": "start event", "title": "Start Event", "description": "Mark event as started"},
                {"id": "lock passes", "title": "Lock Passes", "description": "Stop pass updates"},
                {"id": "close event", "title": "Close Event", "description": "Finalize current event"},
            ],
        },
        {
            "title": "Finance & Support",
            "rows": [
                {"id": "expense", "title": "Add Expense", "description": "Record event expense"},
                {"id": "add sponsor", "title": "Add Sponsor", "description": "Record sponsor contribution"},
                {"id": "refund sponsor", "title": "Refund Sponsor", "description": "Reverse sponsor entry"},
                {"id": "remind", "title": "Remind Flat", "description": "Send payment reminder"},
            ],
        },
    ]


def build_committee_reports_sections() -> list[dict]:
    return [
        {
            "title": "Reports",
            "rows": [
                {"id": "summary", "title": "Summary", "description": "Overall event summary"},
                {"id": "block report", "title": "Block Report", "description": "Building-wise breakdown"},
                {"id": "participation report", "title": "Participation Report", "description": "Committee analytics report"},
                {"id": "report options", "title": "All Report Options", "description": "Browse exportable reports"},
            ],
        }
    ]


def build_committee_more_sections() -> list[dict]:
    """Legacy helper kept for tests; mirrors extended committee actions."""
    return [
        *build_committee_approvals_sections(),
        *build_committee_reports_sections(),
    ]
