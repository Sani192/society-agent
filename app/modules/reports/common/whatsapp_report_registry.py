from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WhatsAppReportRegistryEntry:
    report_code: str
    handler: Callable
    requires_event_id: bool
    normalized_report: str


def normalize_command_key(*, category: str, report: str) -> str:
    normalized_category = (category or "").strip().lower()
    normalized_report = (report or "").strip().lower().replace("_", "-")
    return f"{normalized_category}:{normalized_report}"


def resolve_report_entry(*, registry: dict[str, WhatsAppReportRegistryEntry], category: str, report: str):
    command_key = normalize_command_key(category=category, report=report)
    entry = registry.get(command_key)
    if not entry:
        raise ValueError(f"Unknown report key: {command_key}")
    return command_key, entry


def build_whatsapp_report_registry(*, financial_handler, admin_handler, governance_handler):
    return {
        "financial:event-summary": WhatsAppReportRegistryEntry(
            report_code="EVENT_FINANCIAL_SUMMARY",
            handler=financial_handler,
            requires_event_id=False,
            normalized_report="event-summary",
        ),
        "admin:onboarding-status": WhatsAppReportRegistryEntry(
            report_code="ONBOARDING_STATUS",
            handler=admin_handler,
            requires_event_id=False,
            normalized_report="onboarding-status",
        ),
        "governance:audit": WhatsAppReportRegistryEntry(
            report_code="GOVERNANCE_AUDIT",
            handler=governance_handler,
            requires_event_id=False,
            normalized_report="audit",
        ),
        "governance:audit-summary": WhatsAppReportRegistryEntry(
            report_code="GOVERNANCE_AUDIT",
            handler=governance_handler,
            requires_event_id=False,
            normalized_report="audit",
        ),
    }
