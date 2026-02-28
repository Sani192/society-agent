from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.permissions.report_permissions import REPORT_PERMISSIONS


@dataclass(frozen=True)
class WhatsAppReportDefinition:
    category: str
    report_code: str
    report_key: str
    label: str
    requires_event_id: bool
    supported_formats: tuple[str, ...] = ("csv", "excel", "pdf")
    aliases: tuple[str, ...] = ()


WHATSAPP_REPORT_DEFINITIONS: tuple[WhatsAppReportDefinition, ...] = (
    WhatsAppReportDefinition(
        category="financial",
        report_code="EVENT_FINANCIAL_SUMMARY",
        report_key="event-summary",
        label="Event Financial Summary",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="FLAT_PAYMENTS",
        report_key="flat-payments",
        label="Flat Payments",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="BLOCK_PAYMENTS",
        report_key="block-payments",
        label="Block Payments",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="SPONSOR_CONTRIBUTIONS",
        report_key="sponsor-contributions",
        label="Sponsor Contributions",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="CONTRIBUTION_REFUNDS",
        report_key="contribution-refunds",
        label="Contribution Refunds",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="BALANCE_CONTINUITY",
        report_key="balance-continuity",
        label="Balance Continuity",
        requires_event_id=False,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="MEMBER_REFUNDS",
        report_key="member-refunds",
        label="Member Refunds",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="financial",
        report_code="LEDGER",
        report_key="ledger",
        label="Ledger",
        requires_event_id=True,
    ),
    WhatsAppReportDefinition(
        category="admin",
        report_code="MEMBER_DIRECTORY",
        report_key="member-directory",
        label="Member Directory",
        requires_event_id=False,
    ),
    WhatsAppReportDefinition(
        category="admin",
        report_code="ONBOARDING_STATUS",
        report_key="onboarding-status",
        label="Onboarding Status",
        requires_event_id=False,
    ),
    WhatsAppReportDefinition(
        category="admin",
        report_code="ANNOUNCEMENT_HISTORY",
        report_key="announcement-history",
        label="Announcement History",
        requires_event_id=False,
        supported_formats=("csv", "excel"),
    ),
    WhatsAppReportDefinition(
        category="governance",
        report_code="GOVERNANCE_AUDIT",
        report_key="audit",
        label="Governance Audit",
        requires_event_id=False,
        aliases=("audit-summary",),
    ),
)


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
        normalized_category = (category or "").strip().lower()
        valid_report_keys = list_valid_report_keys_for_category(
            registry=registry,
            category=normalized_category,
        )
        valid_report_key_list = ", ".join(valid_report_keys) if valid_report_keys else "none"
        raise ValueError(
            "Invalid report for category "
            f"'{normalized_category or 'unknown'}'. "
            f"Valid report keys: {valid_report_key_list}. "
            "Try: report options"
        )
    return command_key, entry


def list_valid_categories(*, registry: dict[str, WhatsAppReportRegistryEntry]) -> list[str]:
    return sorted({entry.category for entry in registry.values()})


def list_valid_report_keys_for_category(
    *,
    registry: dict[str, WhatsAppReportRegistryEntry],
    category: str,
) -> list[str]:
    normalized_category = (category or "").strip().lower()
    return sorted(
        {
            entry.report_key
            for entry in registry.values()
            if entry.category == normalized_category
        }
    )


def build_whatsapp_report_registry(*, handlers_by_code: dict[str, Callable]):
    registry: dict[str, WhatsAppReportRegistryEntry] = {}

    for definition in WHATSAPP_REPORT_DEFINITIONS:
        handler = handlers_by_code.get(definition.report_code)
        if not handler:
            continue

        report_variants = (definition.report_key, *definition.aliases)
        for report_variant in report_variants:
            command_key = normalize_command_key(
                category=definition.category,
                report=report_variant,
            )
            registry[command_key] = WhatsAppReportRegistryEntry(
                category=definition.category,
                report_code=definition.report_code,
                report_key=definition.report_key,
                label=definition.label,
                handler=handler,
                requires_event_id=definition.requires_event_id,
                normalized_report=definition.report_key,
                supported_formats=definition.supported_formats,
            )

    return registry


def list_exportable_report_options(
    *,
    registry: dict[str, WhatsAppReportRegistryEntry],
    role: str | None = None,
):
    options = []
    seen_keys = set()

    for command_key, entry in sorted(registry.items()):
        normalized_command_key = normalize_command_key(
            category=entry.category,
            report=entry.report_key,
        )
        if normalized_command_key in seen_keys:
            continue

        if role:
            allowed_roles = REPORT_PERMISSIONS.get(entry.report_code, set())
            if role not in allowed_roles:
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
                "requires_event_id": entry.requires_event_id,
            }
        )

    return options
