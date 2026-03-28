from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
from typing import Any

from app.i18n.catalog import translate

MAIN_MENU_ID = "ui::menu"
MY_ACCOUNT_ID = "ui::my-account"
SOCIETY_ID = "ui::society"
FINANCE_ID = "ui::finance"
REPORTS_ID = "ui::reports"
ADMINISTRATION_ID = "ui::administration"

Translator = Callable[[str], str]
RowSpec = tuple[str, str]
SectionSpec = tuple[str, tuple[RowSpec, ...]]

_MAIN_DASHBOARD_ROWS: tuple[RowSpec, ...] = (
    (MY_ACCOUNT_ID, "dashboard.main.my_account"),
    (SOCIETY_ID, "dashboard.main.society"),
    (FINANCE_ID, "dashboard.main.finance"),
    (REPORTS_ID, "dashboard.main.reports"),
)
_COMMITTEE_DASHBOARD_ROW: RowSpec = (ADMINISTRATION_ID, "dashboard.main.administration")
_MY_ACCOUNT_SECTIONS: tuple[SectionSpec, ...] = (
    (
        "dashboard.my_account.participation_section",
        (
            ("ui::participation", "dashboard.my_account.participation"),
            ("my status", "dashboard.my_account.event_status"),
        ),
    ),
    (
        "dashboard.my_account.finance_section",
        (("ui::payments", "dashboard.my_account.payments"),),
    ),
    (
        "dashboard.my_account.account_section",
        (
            ("ui::language", "dashboard.my_account.language"),
            ("help", "dashboard.my_account.help"),
            ("menu", "dashboard.my_account.menu"),
        ),
    ),
)
_SOCIETY_SECTIONS: tuple[SectionSpec, ...] = (
    (
        "dashboard.society.section_title",
        (
            ("ui::join-society", "dashboard.society.join_society"),
            ("join", "dashboard.society.send_join_request"),
            ("join status", "dashboard.society.join_status"),
        ),
    ),
)
_FINANCE_BASE_ROWS: tuple[RowSpec, ...] = (("ui::payments", "dashboard.finance_sections.payments"),)
_FINANCE_ACTION_ROWS: tuple[RowSpec, ...] = (
    ("ui::make-payment", "dashboard.finance_sections.make_payment"),
    ("ui::request-refund", "dashboard.finance_sections.request_refund"),
    ("pay", "dashboard.finance_sections.pay_dues"),
    ("refund", "dashboard.finance_sections.refund"),
)


def _resolve_translator(*, lang: str | None = None, translator: Translator | None = None) -> Translator:
    if translator is not None:
        return translator
    return partial(translate, lang=lang)


def _build_rows(row_specs: Iterable[RowSpec], translator: Translator) -> list[dict[str, str]]:
    return [
        {
            "id": row_id,
            "title": translator(f"{key_prefix}.title"),
            "description": translator(f"{key_prefix}.description"),
        }
        for row_id, key_prefix in row_specs
    ]


def _build_sections(section_specs: Iterable[SectionSpec], translator: Translator) -> list[dict[str, Any]]:
    return [
        {
            "title": translator(section_title_key),
            "rows": _build_rows(row_specs, translator),
        }
        for section_title_key, row_specs in section_specs
    ]


def build_main_dashboard_sections(
    *,
    is_committee: bool,
    lang: str | None = None,
    translator: Translator | None = None,
) -> list[dict]:
    translate_text = _resolve_translator(lang=lang, translator=translator)
    row_specs = list(_MAIN_DASHBOARD_ROWS)
    if is_committee:
        row_specs.append(_COMMITTEE_DASHBOARD_ROW)
    return [{"title": translate_text("dashboard.sections_title"), "rows": _build_rows(row_specs, translate_text)}]



def build_my_account_sections(*, lang: str | None = None, translator: Translator | None = None) -> list[dict]:
    return _build_sections(_MY_ACCOUNT_SECTIONS, _resolve_translator(lang=lang, translator=translator))



def build_society_sections(*, lang: str | None = None, translator: Translator | None = None) -> list[dict]:
    return _build_sections(_SOCIETY_SECTIONS, _resolve_translator(lang=lang, translator=translator))



def build_finance_sections(
    *,
    include_payment_actions: bool = True,
    lang: str | None = None,
    translator: Translator | None = None,
) -> list[dict]:
    translate_text = _resolve_translator(lang=lang, translator=translator)
    row_specs = list(_FINANCE_BASE_ROWS)
    if include_payment_actions:
        row_specs = [*_FINANCE_ACTION_ROWS[:2], *row_specs, *_FINANCE_ACTION_ROWS[2:]]
    return [{"title": translate_text("dashboard.finance_sections.section_title"), "rows": _build_rows(row_specs, translate_text)}]
