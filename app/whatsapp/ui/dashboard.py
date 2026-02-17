from __future__ import annotations

MAIN_MENU_ID = "ui::menu"
MY_ACCOUNT_ID = "ui::my-account"
SOCIETY_ID = "ui::society"
FINANCE_ID = "ui::finance"
ADMINISTRATION_ID = "ui::administration"


def build_main_dashboard_sections(*, is_committee: bool) -> list[dict]:
    rows = [
        {"id": MY_ACCOUNT_ID, "title": "My Account", "description": "Participation and personal finance"},
        {"id": SOCIETY_ID, "title": "Society", "description": "Join and membership status"},
        {"id": FINANCE_ID, "title": "Finance", "description": "Payments and refunds"},
    ]
    if is_committee:
        rows.append(
            {
                "id": ADMINISTRATION_ID,
                "title": "Administration",
                "description": "Approvals, operations, reports",
            }
        )

    return [{"title": "Sections", "rows": rows}]


def build_my_account_sections() -> list[dict]:
    return [
        {
            "title": "My Account",
            "rows": [
                {"id": "ui::participation", "title": "Participation", "description": "Pass and event status"},
                {"id": "ui::payments", "title": "Payments", "description": "Balance and history"},
                {"id": "help", "title": "Help", "description": "Usage help"},
                {"id": "commands", "title": "Commands", "description": "List all commands"},
                {"id": "menu", "title": "Main Menu", "description": "Open dashboard again"},
                {"id": "my refund requests", "title": "Refunds", "description": "My refund requests"},
                {"id": "my status", "title": "Event Status", "description": "Current event standing"},
            ],
        }
    ]


def build_society_sections() -> list[dict]:
    return [
        {
            "title": "Society",
            "rows": [
                {"id": "ui::join-society", "title": "Join Society", "description": "Link your flat"},
                {"id": "join", "title": "Join (Template)", "description": "Command template for joining"},
                {"id": "link member", "title": "Link Member", "description": "Link existing member profile"},
                {"id": "verify phone", "title": "Verify Phone", "description": "Verify phone ownership"},
                {"id": "join status", "title": "Join Status", "description": "Track your request"},
            ],
        }
    ]


def build_finance_sections() -> list[dict]:
    return [
        {
            "title": "Finance",
            "rows": [
                {"id": "ui::make-payment", "title": "Make Payment", "description": "Pay outstanding amount"},
                {"id": "ui::request-refund", "title": "Request Refund", "description": "Initiate a refund"},
                {"id": "refund", "title": "Refund Status", "description": "Track or check refund requests"},
            ],
        }
    ]
