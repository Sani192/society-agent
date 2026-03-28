"""Report-specific WhatsApp interaction flow."""

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.channels.whatsapp.ui_router import (
    REPORT_INTENTS_REQUIRING_EVENT,
    WHATSAPP_LIST_MAX_ROWS,
    WHATSAPP_MORE_REPORTS_ROW_ID,
    WHATSAPP_REPORT_EVENT_ROW_PREFIX,
    _chunk_report_options,
    _default_report_event_id,
    _get_latest_event_in_context,
    _next_report_page,
    _normalize_report_page,
    _parse_report_event_selection,
    _recent_report_events,
    _report_page_option_limit,
)
from app.db.session import SessionLocal
from app.i18n.catalog import translate
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_exportable_report_options,
    resolve_report_entry,
)
from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService
from app.modules.users.language_service import resolve_sender_language
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.channels.whatsapp.ui.reports import build_report_event_sections
from app.channels.whatsapp.export_session import (
    ExportSessionState,
    build_export_session_key,
    get_export_session,
    save_export_session,
)
from app.channels.whatsapp.intents import WHATSAPP_INTENTS
from app.channels.whatsapp.router import detect_whatsapp_intent


def _build_reports_list_sections(
    options: list[dict],
    *,
    page_index: int = 0,
    page_size: int = WHATSAPP_LIST_MAX_ROWS,
    include_more_row: bool = False,
    lang: str | None = None,
) -> list[dict]:
    effective_page_size = (
        _report_page_option_limit(total_options=len(options), page_size=page_size)
        if include_more_row
        else page_size
    )
    option_pages = _chunk_report_options(options, page_size=effective_page_size)
    if not option_pages:
        return []

    normalized_page = _normalize_report_page(
        page_index=page_index,
        total_pages=len(option_pages),
    )
    page_options = option_pages[normalized_page]
    grouped: dict[str, list[dict]] = {}
    for option in page_options:
        grouped.setdefault(option["category"], []).append(option)

    sections: list[dict] = []
    for category in sorted(grouped):
        rows = [
            {
                "id": f"export::{option['command_key']}",
                "title": option["label"][:24],
                "description": translate(
                    "report_flow.row_description",
                    lang,
                    category=category.title(),
                ),
            }
            for option in grouped[category]
        ]
        if rows:
            sections.append({"title": category.title(), "rows": rows})

    if include_more_row:
        sections.append(
            {
                "title": translate("report_flow.more_section_title", lang),
                "rows": [
                    {
                        "id": WHATSAPP_MORE_REPORTS_ROW_ID,
                        "title": translate("report_flow.more_reports_title", lang),
                        "description": translate(
                            "report_flow.more_reports_description",
                            lang,
                        ),
                    }
                ],
            }
        )
    return sections


def handle_report_flow(*, client, message) -> bool:
    intent = detect_whatsapp_intent(message.text)
    requested_more_reports = message.text.strip().lower() == WHATSAPP_MORE_REPORTS_ROW_ID
    selected_report_event_id = _parse_report_event_selection(message.text)

    if intent in REPORT_INTENTS_REQUIRING_EVENT:
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            member = ensure_committee_member(
                canonical_sender,
                db,
                channel_type="whatsapp",
                external_user_id=message.sender_id,
            )
            lang = resolve_sender_language(
                db,
                sender_id=canonical_sender,
                channel="whatsapp",
            )
            latest_event = _get_latest_event_in_context(
                db=db,
                society_id=member.society_id,
            )
            default_event_id = _default_report_event_id(latest_event)
            if not default_event_id:
                session_key = build_export_session_key(
                    member_id=str(member.id),
                    sender_id=canonical_sender,
                )
                session = get_export_session(session_key)
                save_export_session(
                    session_key,
                    ExportSessionState(
                        options=session.options if session else [],
                        current_page=session.current_page if session else 0,
                        event_id=None,
                        pending_intent=intent,
                    ),
                )
                events = _recent_report_events(db=db, society_id=member.society_id)
                client.send_list_message(
                    to_phone=message.sender_id,
                    header_text=translate("report_flow.header", lang),
                    body_text=translate("report_flow.event_required", lang),
                    button_text=translate("report_flow.choose_event", lang),
                    sections=build_report_event_sections(
                        events,
                        row_prefix=WHATSAPP_REPORT_EVENT_ROW_PREFIX,
                        lang=lang,
                    ),
                )
                return True
        finally:
            db.close()

    if (
        intent == "REPORT_OPTIONS"
        or requested_more_reports
        or selected_report_event_id
        or (message.text or "").strip().lower().startswith("export::")
    ):
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            member = ensure_committee_member(
                canonical_sender,
                db,
                channel_type="whatsapp",
                external_user_id=message.sender_id,
            )
            lang = resolve_sender_language(
                db,
                sender_id=canonical_sender,
                channel="whatsapp",
            )
            report_options = list_exportable_report_options(
                registry=build_whatsapp_report_registry(
                    handlers_by_code=WhatsAppReportExportService.handlers_by_report_code()
                ),
                role=str(member.role) if member.role is not None else None,
                lang=lang,
            )
            session_key = build_export_session_key(
                member_id=str(member.id),
                sender_id=canonical_sender,
            )
            session = get_export_session(session_key)

            if intent == "REPORT_OPTIONS":
                latest_event = _get_latest_event_in_context(
                    db=db,
                    society_id=member.society_id,
                )
                save_export_session(
                    session_key,
                    ExportSessionState(
                        options=report_options,
                        current_page=0,
                        event_id=_default_report_event_id(latest_event),
                    ),
                )
                sections = _build_reports_list_sections(
                    report_options,
                    page_index=0,
                    include_more_row=len(report_options) > WHATSAPP_LIST_MAX_ROWS,
                    lang=lang,
                )
                client.send_list_message(
                    to_phone=message.sender_id,
                    header_text=translate("report_flow.header", lang),
                    body_text=translate("report_flow.pick_category", lang),
                    button_text=translate("report_flow.choose_report", lang),
                    sections=sections,
                )
                return True

            if selected_report_event_id:
                pending_intent = session.pending_intent if session else None
                save_export_session(
                    session_key,
                    ExportSessionState(
                        options=report_options,
                        current_page=0,
                        event_id=selected_report_event_id,
                        pending_intent=pending_intent,
                    ),
                )
                if pending_intent:
                    intent_keyword = WHATSAPP_INTENTS.get(pending_intent, "").strip()
                    if intent_keyword:
                        reply_text = handle_inbound_message(
                            InboundMessage(
                                channel=message.channel,
                                sender_id=message.sender_id,
                                display_name=message.display_name,
                                text=intent_keyword,
                                metadata=message.metadata,
                            )
                        )
                        client.send_text_message(message.sender_id, reply_text)
                        return True
                sections = _build_reports_list_sections(
                    report_options,
                    page_index=0,
                    include_more_row=len(report_options) > WHATSAPP_LIST_MAX_ROWS,
                    lang=lang,
                )
                client.send_list_message(
                    to_phone=message.sender_id,
                    header_text=translate("report_flow.header", lang),
                    body_text=translate("report_flow.pick_report", lang),
                    button_text=translate("report_flow.choose_report", lang),
                    sections=sections,
                )
                return True

            if (
                (message.text or "").strip().lower().startswith("export::")
                and not requested_more_reports
                and session
                and session.options
            ):
                selected_command_key = (
                    (message.text or "").strip().lower().removeprefix("export::")
                )
                selected_option = next(
                    (
                        opt
                        for opt in session.options
                        if (opt.get("command_key") or "").lower() == selected_command_key
                    ),
                    None,
                )
                if selected_option:
                    registry = build_whatsapp_report_registry(
                        handlers_by_code=WhatsAppReportExportService.handlers_by_report_code()
                    )
                    _command_key, entry = resolve_report_entry(
                        registry=registry,
                        category=selected_option["category"],
                        report=selected_option["report_key"],
                    )
                    if entry.requires_event_id and not session.event_id:
                        events = _recent_report_events(db=db, society_id=member.society_id)
                        valid_event_ids = [
                            _default_report_event_id(event) for event in events
                        ]
                        valid_event_ids = [
                            event_id for event_id in valid_event_ids if event_id
                        ]
                        if len(valid_event_ids) == 1:
                            save_export_session(
                                session_key,
                                ExportSessionState(
                                    options=report_options,
                                    current_page=session.current_page,
                                    event_id=valid_event_ids[0],
                                    pending_intent=session.pending_intent,
                                ),
                            )
                            return False
                        client.send_list_message(
                            to_phone=message.sender_id,
                            header_text=translate("report_flow.header", lang),
                            body_text=translate("report_flow.event_required", lang),
                            button_text=translate("report_flow.choose_event", lang),
                            sections=build_report_event_sections(
                                events,
                                row_prefix=WHATSAPP_REPORT_EVENT_ROW_PREFIX,
                                lang=lang,
                            ),
                        )
                        return True

            if requested_more_reports:
                current_page = session.current_page if session else 0
                include_more_row = len(report_options) > WHATSAPP_LIST_MAX_ROWS
                option_pages = _chunk_report_options(
                    report_options,
                    page_size=(
                        _report_page_option_limit(
                            total_options=len(report_options),
                            page_size=WHATSAPP_LIST_MAX_ROWS,
                        )
                        if include_more_row
                        else WHATSAPP_LIST_MAX_ROWS
                    ),
                )
                if option_pages:
                    current_page = _next_report_page(
                        current_page=current_page,
                        total_pages=len(option_pages),
                    )
                save_export_session(
                    session_key,
                    ExportSessionState(
                        options=report_options,
                        current_page=current_page,
                        event_id=session.event_id if session else None,
                    ),
                )
                sections = _build_reports_list_sections(
                    report_options,
                    page_index=current_page,
                    include_more_row=include_more_row,
                    lang=lang,
                )
                if sections:
                    client.send_list_message(
                        to_phone=message.sender_id,
                        header_text=translate("report_flow.header", lang),
                        body_text=translate("report_flow.pick_category", lang),
                        button_text=translate("report_flow.choose_report", lang),
                        sections=sections,
                    )
                    return True
        except Exception:
            logger.exception("Failed in report flow")
        finally:
            db.close()
    return False
