from __future__ import annotations


def build_participation_sections(*, include_add_pass: bool = True) -> list[dict]:
    rows = [
        {"id": "my pass", "title": "View My Pass", "description": "Current pass details"},
        {"id": "my tokens", "title": "View My Tokens", "description": "See active/served tokens"},
        {"id": "my status", "title": "Event Status", "description": "Participation and payment state"},
    ]
    if include_add_pass:
        rows = [
            {
                "id": "ui::participation:add-update-pass",
                "title": "Add / Update Pass",
                "description": "Update food counts",
            },
            {"id": "add pass", "title": "Add Pass", "description": "Command-based pass update"},
            *rows,
        ]

    return [{"title": "Participation", "rows": rows}]


def add_or_update_pass_prompt() -> str:
    return "Enter food counts.\nExample:\nveg 2 jain 1 kids 1"
