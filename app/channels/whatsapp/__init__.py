"""Canonical WhatsApp channel package.

Import WhatsApp functionality via this package boundary to keep channel-layer
modules isolated from other application layers.
"""

from importlib import import_module

__all__ = [
    "adapter",
    "approval_flow",
    "client",
    "constants",
    "intents",
    "report_flow",
    "response_templates",
    "router",
    "session_flows",
    "ui",
    "ui_router",
    "committee_action_session",
    "committee_management_session",
    "event_creation_session",
    "export_session",
    "finance_action_session",
    "join_session",
]


def __getattr__(name: str):
    if name in __all__:
        return import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
