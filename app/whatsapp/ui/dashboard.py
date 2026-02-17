from __future__ import annotations

MAIN_MENU_ID = "ui::menu"
MY_ACCOUNT_ID = "ui::my-account"
SOCIETY_ID = "ui::society"
FINANCE_ID = "ui::finance"
ADMINISTRATION_ID = "ui::administration"


def build_main_dashboard_sections(*, is_committee: bool) -> list[dict]:
    sections = [
        {
            "title": "My Account",
            "rows": [
                {"id": "ui::participation", "title": "Participation", "description": "Passes and event status"},
                {"id": "ui::payments", "title": "Payments", "description": "Balance and payment history"},
                {"id": "my refund requests", "title": "Refunds", "description": "Track refund requests"},
                {"id": "my status", "title": "Event Status", "description": "Current participation status"},
            ],
        },
        {
            "title": "Society",
            "rows": [
                {"id": "ui::join-society", "title": "Join Society", "description": "Link your flat"},
                {"id": "join status", "title": "Join Status", "description": "Check join request status"},
            ],
        },
        {
            "title": "Finance",
            "rows": [
                {"id": "ui::make-payment", "title": "Make Payment", "description": "Submit payment"},
                {"id": "ui::request-refund", "title": "Request Refund", "description": "Initiate refund"},
            ],
        },
    ]

    if is_committee:
        sections.append(
            {
                "title": "Administration",
                "rows": [
                    {"id": "payment requests", "title": "Approvals", "description": "Payment and refund requests"},
                    {"id": "expense", "title": "Expenses", "description": "Add event expenses"},
                    {"id": "add sponsor", "title": "Sponsors", "description": "Manage sponsors"},
                    {"id": "report options", "title": "Reports", "description": "Financial and audit exports"},
                ],
            }
        )
    return sections
