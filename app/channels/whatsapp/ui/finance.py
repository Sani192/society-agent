from __future__ import annotations


def build_payments_sections() -> list[dict]:
    return [
        {
            "title": "Payments",
            "rows": [
                {"id": "ui::finance:view-balance", "title": "View Balance", "description": "Current ledger"},
                {"id": "my balance", "title": "My Balance", "description": "Show current balance using command"},
                {"id": "my payments", "title": "View Payment History", "description": "All transactions"},
                {
                    "id": "my payment requests",
                    "title": "My Payment Requests",
                    "description": "Pending and approved requests",
                },
                {"id": "my refund requests", "title": "My Refund Requests", "description": "Track submitted refunds"},
            ],
        }
    ]


def build_make_payment_sections(*, outstanding_amount: str) -> list[dict]:
    return [
        {
            "title": "Make Payment",
            "rows": [
                {"id": f"pay {outstanding_amount}", "title": "Pay Full Amount", "description": "Submit full outstanding"},
                {"id": "pay", "title": "Pay Dues", "description": "Send: pay <amount>"},
                {
                    "id": "ui::finance:pay-custom",
                    "title": "Pay Custom Amount",
                    "description": "Enter preferred amount",
                },
            ],
        }
    ]


def payment_custom_amount_prompt() -> str:
    return (
        "Please reply with payment amount only.\n"
        "Example:\n"
        "500\n\n"
        "Expected next reply: a number only.\n"
        "Type `cancel` to stop."
    )


def refund_request_prompt() -> str:
    return (
        "Please reply with refund amount and reason.\n"
        "Example:\n"
        "200 guest absent\n\n"
        "Expected next reply: amount followed by reason.\n"
        "Type `cancel` to stop."
    )


def format_financial_overview(*, expected: str, paid: str, refunded: str, outstanding: str) -> str:
    return "\n".join(
        [
            "Your Financial Overview",
            "",
            f"Expected: {expected}",
            f"Paid: {paid}",
            f"Refunded: {refunded}",
            f"Outstanding: {outstanding}",
        ]
    )
