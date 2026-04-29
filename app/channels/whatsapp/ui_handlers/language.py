from app.channels.whatsapp import ui_router
CMDS={"ui::language"}
def can_handle(msg:str)->bool:return msg in CMDS or msg.startswith(ui_router.LANGUAGE_ROW_PREFIX)
def handle(*,client,message,context)->bool:return ui_router._try_handle_ui_message_legacy(client=client,message=message)
