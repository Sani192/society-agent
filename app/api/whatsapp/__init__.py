"""Backward-compatible exports for WhatsApp API module.

This package keeps `app.api.whatsapp` monkeypatch targets compatible with the
previous single-module layout used heavily by tests.
"""

from app.config import settings
from app.commands.handlers.common import get_latest_event

from app.api.whatsapp import webhook as _webhook
from app.channels.whatsapp import approval_flow as _approval_flow
from app.channels.whatsapp import report_flow as _report_flow
from app.channels.whatsapp import session_flows as _session_flows
from app.channels.whatsapp import ui_router as _ui_router

# Keep explicit legacy monkeypatch targets exported from this module.
_compat_exports_anchor = (settings, get_latest_event)


# Re-export symbols for compatibility.
for _name in dir(_webhook):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_webhook, _name)

for _name in dir(_ui_router):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_ui_router, _name)

for _name in dir(_session_flows):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_session_flows, _name)

for _name in dir(_report_flow):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_report_flow, _name)

for _name in dir(_approval_flow):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_approval_flow, _name)

# Explicit export for static type checkers.
router = _webhook.router


def _sync_compat_symbols() -> None:
    """Propagate patched module-level symbols into split submodules."""
    sync_map = {
        _webhook: [
            "_ensure_channel_enabled",
            "_verify_signature",
            "parse_webhook_payload",
            "get_whatsapp_client",
            "handle_inbound_message",
            "SessionLocal",
            "detect_whatsapp_intent",
            "ensure_committee_member",
            "list_exportable_report_options",
            "get_latest_event",
            "_recent_report_events",
            "_try_handle_ui_message",
            "handle_report_flow",
            "handle_session_flow",
        ],
        _ui_router: [
            "SessionLocal",
            "ensure_committee_member",
            "ensure_member_of_society",
            "resolve_flat",
            "resolve_sender_society_id",
            "get_latest_event",
            "get_latest_event_for_society",
            "_is_registered_member_for_sender",
            "_recent_member_events",
            "_is_committee_member",
            "_get_committee_member",
            "_button_row",
            "UserQueryService",
            "AdminOnboardingQueryService",
            "PaymentRequestService",
            "RefundRequestService",
            "_is_committee_member",
            "_get_committee_member",
            "_get_latest_event_in_context",
            "list_exportable_report_options",
            "build_whatsapp_report_registry",
            "WhatsAppReportExportService",
            "handle_inbound_message",
            "detect_whatsapp_intent",
        ],
        _session_flows: [
            "SessionLocal",
            "handle_inbound_message",
            "JoinCodeService",
            "parse_pass_counts",
            "Event",
            "_try_handle_ui_message",
        ],
        _report_flow: [
            "SessionLocal",
            "ensure_committee_member",
            "list_exportable_report_options",
            "build_whatsapp_report_registry",
            "resolve_report_entry",
            "WhatsAppReportExportService",
            "handle_inbound_message",
            "detect_whatsapp_intent",
            "WHATSAPP_INTENTS",
            "_recent_report_events",
            "_get_latest_event_in_context",
            "_default_report_event_id",
            "_parse_report_event_selection",
        ],
        _approval_flow: [
            "ensure_committee_member",
            "get_latest_event",
            "get_latest_event_for_society",
            "AdminOnboardingQueryService",
            "PaymentRequestService",
            "RefundRequestService",
            "_is_committee_member",
            "_get_committee_member",
            "_get_latest_event_in_context",
        ],
    }

    for module, names in sync_map.items():
        for name in names:
            if name in globals():
                setattr(module, name, globals()[name])


async def whatsapp_webhook_event(request):
    _sync_compat_symbols()
    return await _webhook.whatsapp_webhook_event(request)


def whatsapp_webhook_verify(*args, **kwargs):
    _sync_compat_symbols()
    return _webhook.whatsapp_webhook_verify(*args, **kwargs)


def whatsapp_webhook(payload):
    _sync_compat_symbols()
    return _webhook.whatsapp_webhook(payload)


__all__ = [n for n in globals() if not n.startswith("__")]
