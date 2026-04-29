from app.channels.whatsapp import ui_router
CMDS={"ui::payments","ui::finance:view-balance","ui::make-payment","ui::finance:pay-custom","ui::request-refund"}
def can_handle(msg:str)->bool:return msg in CMDS
def handle(*,client,message,context)->bool:return ui_router._try_handle_ui_message_legacy(client=client,message=message)
