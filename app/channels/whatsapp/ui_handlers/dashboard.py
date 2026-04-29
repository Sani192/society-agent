from app.channels.whatsapp import ui_router

CMDS={"menu","help","ui::menu","ui::menu:more","ui::my-account","ui::society","ui::join-society","ui::finance","ui::administration","ui::administration:approvals","ui::administration:operations","ui::administration:operations:more","ui::administration:reports","ui::administration:committee","ui::administration:food"}
def can_handle(msg:str)->bool:return msg in CMDS
def handle(*,client,message,context)->bool:return ui_router._try_handle_ui_message_legacy(client=client,message=message)
