import asyncio

import app.api.whatsapp as whatsapp_api
from app.api.whatsapp import webhook as webhook_module
from app.channels.whatsapp import report_flow


def test_sync_compat_symbols_propagates_patched_values(monkeypatch):
    def sentinel():
        return None

    monkeypatch.setattr(whatsapp_api, "_ensure_channel_enabled", sentinel)

    whatsapp_api._sync_compat_symbols()

    assert webhook_module._ensure_channel_enabled is sentinel


def test_whatsapp_webhook_event_wrapper_syncs_before_delegate(monkeypatch):
    def sentinel():
        return None

    async def fake_delegate(_request):
        assert webhook_module._ensure_channel_enabled is sentinel
        return {"status": "ok"}

    monkeypatch.setattr(whatsapp_api, "_ensure_channel_enabled", sentinel)
    monkeypatch.setattr(webhook_module, "whatsapp_webhook_event", fake_delegate)

    response = asyncio.run(whatsapp_api.whatsapp_webhook_event(object()))
    assert response == {"status": "ok"}


def test_build_reports_list_sections_wrapper_delegates_to_report_flow(monkeypatch):
    called = {}

    def fake_impl(options, *, page_index=0, page_size=10, include_more_row=False):
        called["args"] = (options, page_index, page_size, include_more_row)
        return [{"title": "Mock", "rows": []}]

    monkeypatch.setattr(report_flow, "_build_reports_list_sections", fake_impl)

    result = webhook_module._build_reports_list_sections(
        [{"category": "x", "command_key": "a", "label": "A", "report_key": "r"}],
        page_index=2,
        page_size=5,
        include_more_row=True,
    )

    assert result == [{"title": "Mock", "rows": []}]
    assert called["args"][1:] == (2, 5, True)


def test_report_flow_build_reports_list_sections_adds_more_row():
    options = [
        {"category": "finance", "command_key": f"k{i}", "label": f"Label {i}", "report_key": f"r{i}"}
        for i in range(11)
    ]

    sections = report_flow._build_reports_list_sections(options, include_more_row=True)

    assert sections[-1]["title"] == "More"
    assert sections[-1]["rows"][0]["id"] == report_flow.WHATSAPP_MORE_REPORTS_ROW_ID
