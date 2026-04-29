CMDS = {"ui::language"}
PFX = "language::"

def can_handle(msg: str) -> bool:
    return msg in CMDS or msg.startswith(PFX)

def handle(*, client, message, context) -> bool:
    from app.channels.whatsapp import ui_router
    return ui_router._try_handle_ui_message_legacy(client=client, message=message)
