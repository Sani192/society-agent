from types import SimpleNamespace
from app.channels.whatsapp.ui_handlers import dashboard, participation, payments, committee, food_ops, reports, language


def test_can_handle_dashboard():
    assert dashboard.can_handle("ui::menu")


def test_can_handle_participation():
    assert participation.can_handle("ui::participation:add-update-pass")


def test_can_handle_payments():
    assert payments.can_handle("ui::make-payment")


def test_can_handle_committee_prefix():
    assert committee.can_handle("committee-member::123")


def test_can_handle_food_prefix():
    assert food_ops.can_handle("food-token-status::abc")


def test_can_handle_reports():
    assert reports.can_handle("ui::reports")


def test_can_handle_language_prefix():
    assert language.can_handle("language::hi")
