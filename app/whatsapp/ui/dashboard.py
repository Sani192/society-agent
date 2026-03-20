from __future__ import annotations

from app.i18n.catalog import translate

MAIN_MENU_ID = "ui::menu"
MY_ACCOUNT_ID = "ui::my-account"
SOCIETY_ID = "ui::society"
FINANCE_ID = "ui::finance"
REPORTS_ID = "ui::reports"
ADMINISTRATION_ID = "ui::administration"


def build_main_dashboard_sections(*, is_committee: bool, lang: str | None = None) -> list[dict]:
    rows = [
        {
            "id": MY_ACCOUNT_ID,
            "title": translate("dashboard.main.my_account.title", lang),
            "description": translate("dashboard.main.my_account.description", lang),
        },
        {
            "id": SOCIETY_ID,
            "title": translate("dashboard.main.society.title", lang),
            "description": translate("dashboard.main.society.description", lang),
        },
        {
            "id": FINANCE_ID,
            "title": translate("dashboard.main.finance.title", lang),
            "description": translate("dashboard.main.finance.description", lang),
        },
        {
            "id": REPORTS_ID,
            "title": translate("dashboard.main.reports.title", lang),
            "description": translate("dashboard.main.reports.description", lang),
        },
    ]
    if is_committee:
        rows.append(
            {
                "id": ADMINISTRATION_ID,
                "title": translate("dashboard.main.administration.title", lang),
                "description": translate("dashboard.main.administration.description", lang),
            }
        )

    return [{"title": translate("dashboard.sections_title", lang), "rows": rows}]


def build_my_account_sections(*, lang: str | None = None) -> list[dict]:
    return [
        {
            "title": translate("dashboard.my_account.participation_section", lang),
            "rows": [
                {
                    "id": "ui::participation",
                    "title": translate("dashboard.my_account.participation.title", lang),
                    "description": translate("dashboard.my_account.participation.description", lang),
                },
                {
                    "id": "my status",
                    "title": translate("dashboard.my_account.event_status.title", lang),
                    "description": translate("dashboard.my_account.event_status.description", lang),
                },
            ],
        },
        {
            "title": translate("dashboard.my_account.finance_section", lang),
            "rows": [
                {
                    "id": "ui::payments",
                    "title": translate("dashboard.my_account.payments.title", lang),
                    "description": translate("dashboard.my_account.payments.description", lang),
                },
            ],
        },
        {
            "title": translate("dashboard.my_account.account_section", lang),
            "rows": [
                {
                    "id": "ui::language",
                    "title": translate("dashboard.my_account.language.title", lang),
                    "description": translate("dashboard.my_account.language.description", lang),
                },
                {
                    "id": "help",
                    "title": translate("dashboard.my_account.help.title", lang),
                    "description": translate("dashboard.my_account.help.description", lang),
                },
                {
                    "id": "menu",
                    "title": translate("dashboard.my_account.menu.title", lang),
                    "description": translate("dashboard.my_account.menu.description", lang),
                },
            ],
        },
    ]


def build_society_sections(*, lang: str | None = None) -> list[dict]:
    return [
        {
            "title": translate("dashboard.society.section_title", lang),
            "rows": [
                {
                    "id": "ui::join-society",
                    "title": translate("dashboard.society.join_society.title", lang),
                    "description": translate("dashboard.society.join_society.description", lang),
                },
                {
                    "id": "join",
                    "title": translate("dashboard.society.send_join_request.title", lang),
                    "description": translate("dashboard.society.send_join_request.description", lang),
                },
                {
                    "id": "join status",
                    "title": translate("dashboard.society.join_status.title", lang),
                    "description": translate("dashboard.society.join_status.description", lang),
                },
            ],
        }
    ]


def build_finance_sections(*, include_payment_actions: bool = True, lang: str | None = None) -> list[dict]:
    rows = [
        {
            "id": "ui::payments",
            "title": translate("dashboard.finance_sections.payments.title", lang),
            "description": translate("dashboard.finance_sections.payments.description", lang),
        },
    ]
    if include_payment_actions:
        rows = [
            {
                "id": "ui::make-payment",
                "title": translate("dashboard.finance_sections.make_payment.title", lang),
                "description": translate("dashboard.finance_sections.make_payment.description", lang),
            },
            {
                "id": "ui::request-refund",
                "title": translate("dashboard.finance_sections.request_refund.title", lang),
                "description": translate("dashboard.finance_sections.request_refund.description", lang),
            },
            *rows,
            {
                "id": "pay",
                "title": translate("dashboard.finance_sections.pay_dues.title", lang),
                "description": translate("dashboard.finance_sections.pay_dues.description", lang),
            },
            {
                "id": "refund",
                "title": translate("dashboard.finance_sections.refund.title", lang),
                "description": translate("dashboard.finance_sections.refund.description", lang),
            },
        ]

    return [{"title": translate("dashboard.finance_sections.section_title", lang), "rows": rows}]
