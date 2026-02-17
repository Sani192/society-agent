from __future__ import annotations


def build_participation_sections() -> list[dict]:
    return [
        {
            "title": "Participation",
            "rows": [
                {
                    "id": "ui::participation:add-update-pass",
                    "title": "Add / Update Pass",
                    "description": "Update food counts",
                },
                {"id": "add pass", "title": "Add Pass", "description": "Command-based pass update"},
                {"id": "my pass", "title": "View My Pass", "description": "Current pass details"},
                {"id": "my status", "title": "Event Status", "description": "Participation and payment state"},
            ],
        }
    ]


def add_or_update_pass_prompt() -> str:
    return "Enter food counts.\nExample:\nveg 2 jain 1 kids 1"
