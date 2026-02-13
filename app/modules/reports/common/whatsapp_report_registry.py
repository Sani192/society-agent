from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WhatsAppReportRegistryEntry:
    category: str
    report_code: str
    report_key: str
    label: str
    handler: Callable
    requires_event_id: bool
    normalized_report: str
    supported_formats: tuple[str, ...]


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
            category="financial",
            report_code="EVENT_FINANCIAL_SUMMARY",
            report_key="event-summary",
            label="Event Financial Summary",
            handler=financial_handler,
            requires_event_id=False,
            normalized_report="event-summary",
            supported_formats=("csv", "excel", "pdf"),
        ),
        "admin:onboarding-status": WhatsAppReportRegistryEntry(
            category="admin",
            report_code="ONBOARDING_STATUS",
            report_key="onboarding-status",
            label="Onboarding Status",
            handler=admin_handler,
            requires_event_id=False,
            normalized_report="onboarding-status",
            supported_formats=("csv", "excel", "pdf"),
        ),
        "governance:audit": WhatsAppReportRegistryEntry(
            category="governance",
            report_code="GOVERNANCE_AUDIT",
            report_key="audit",
            label="Governance Audit",
            handler=governance_handler,
            requires_event_id=False,
            normalized_report="audit",
            supported_formats=("csv", "excel", "pdf"),
        ),
        "governance:audit-summary": WhatsAppReportRegistryEntry(
            category="governance",
            report_code="GOVERNANCE_AUDIT",
            report_key="audit",
            label="Governance Audit",
            handler=governance_handler,
            requires_event_id=False,
            normalized_report="audit",
            supported_formats=("csv", "excel", "pdf"),
        ),
    }


def list_exportable_report_options(*, registry: dict[str, WhatsAppReportRegistryEntry]):
    options = []
    seen_keys = set()

    for command_key, entry in sorted(registry.items()):
        normalized_command_key = normalize_command_key(
            category=entry.category,
            report=entry.report_key,
        )
        if normalized_command_key in seen_keys:
            continue
        seen_keys.add(normalized_command_key)

        options.append(
            {
                "category": entry.category,
                "report_key": entry.report_key,
                "label": entry.label,
                "supported_formats": list(entry.supported_formats),
                "example_command": (
                    "report export "
                    f"--category {entry.category} "
                    f"--report {entry.report_key} "
                    f"--format {entry.supported_formats[0]}"
                ),
                "command_key": command_key,
            }
        )

    return options
