from __future__ import annotations

MAIN_MENU_ID = "ui::menu"
MY_ACCOUNT_ID = "ui::my-account"
SOCIETY_ID = "ui::society"
FINANCE_ID = "ui::finance"
REPORTS_ID = "ui::reports"
ADMINISTRATION_ID = "ui::administration"


def build_main_dashboard_sections(*, is_committee: bool) -> list[dict]:
    rows = [
        {"id": MY_ACCOUNT_ID, "title": "My Account", "description": "Check participation, dues, and support"},
        {"id": SOCIETY_ID, "title": "Society", "description": "Join your society and track membership"},
        {"id": FINANCE_ID, "title": "Finance", "description": "Track dues & refunds"},
        {"id": REPORTS_ID, "title": "Reports", "description": "View society reports"},
    ]
    if is_committee:
        rows.append(
            {
                "id": ADMINISTRATION_ID,
                "title": "Administration",
                "description": "Manage approvals and event operations",
            }
        )

    return [{"title": "Sections", "rows": rows}]


def build_my_account_sections() -> list[dict]:
    return [
        {
            "title": "Participation",
            "rows": [
                {"id": "ui::participation", "title": "Participation", "description": "Check pass and event status"},
                {"id": "my status", "title": "Event Status", "description": "View your current event standing"},
            ],
        },
        {
            "title": "Finance",
            "rows": [
                {"id": "ui::payments", "title": "Payments", "description": "Track balance, history, and refunds"},
            ],
        },
        {
            "title": "My Account",
            "rows": [
                {"id": "help", "title": "Help", "description": "Get guidance on what to send"},
                                {"id": "menu", "title": "Main Menu", "description": "Open dashboard again"},
            ],
        }
    ]


def build_society_sections() -> list[dict]:
    return [
        {
            "title": "Society",
            "rows": [
                {"id": "ui::join-society", "title": "Join Society", "description": "Start your membership request"},
                {"id": "join", "title": "Send Join Request", "description": "Send: join <join_code> <flat>"},
                {"id": "join status", "title": "Join Status", "description": "Track your request"},
            ],
        }
    ]


def build_finance_sections(*, include_payment_actions: bool = True) -> list[dict]:
    rows = [
        {"id": "ui::payments", "title": "Payments", "description": "View balance, history, and refund requests"},
    ]
    if include_payment_actions:
        rows = [
            {"id": "ui::make-payment", "title": "Make Payment", "description": "Pay your outstanding dues"},
            {"id": "ui::request-refund", "title": "Request Refund", "description": "Start a new refund request"},
            *rows,
            {"id": "pay", "title": "Pay Dues", "description": "Send: pay <amount>"},
            {"id": "refund", "title": "Request a Refund", "description": "Send: refund <amount> <reason>"},
        ]

    return [{"title": "Finance", "rows": rows}]
