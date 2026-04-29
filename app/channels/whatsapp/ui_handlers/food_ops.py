CMDS = {"verify food token", "scan food qr", "token status", "serve flat", "flat passes"}
PFX = ("food-verify-token::", "food-scan-qr::", "food-token-status::", "food-serve-flat::", "food-flat-status::")

def can_handle(msg: str) -> bool:
    return msg in CMDS or any(msg.startswith(p) for p in PFX)

def handle(*, client, message, context) -> bool:
    from app.channels.whatsapp import ui_router
    return ui_router._try_handle_ui_message_legacy(client=client, message=message)
