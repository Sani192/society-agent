CMDS = {"ui::approve-user", "ui::approve-payment", "ui::approve-refund", "committee::view", "committee::add", "committee::remove", "committee::change-role"}
PFX = ("committee-add-member::", "committee-member::", "committee-role::", "committee-confirm::")

def can_handle(msg: str) -> bool:
    return msg in CMDS or any(msg.startswith(p) for p in PFX)

def handle(*, client, message, context) -> bool:
    from app.channels.whatsapp import ui_router
    return ui_router._try_handle_ui_message_legacy(client=client, message=message)
