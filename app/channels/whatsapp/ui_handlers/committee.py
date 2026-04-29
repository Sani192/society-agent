from app.channels.whatsapp import ui_router
PFX=(ui_router.COMMITTEE_ADD_MEMBER_ROW_PREFIX,ui_router.COMMITTEE_MEMBER_ROW_PREFIX,ui_router.COMMITTEE_ROLE_ROW_PREFIX,ui_router.COMMITTEE_CONFIRM_ROW_PREFIX)
CMDS={"ui::approve-user","ui::approve-payment","ui::approve-refund","committee::view","committee::add","committee::remove","committee::change-role"}
def can_handle(msg:str)->bool:return msg in CMDS or any(msg.startswith(p) for p in PFX)
def handle(*,client,message,context)->bool:return ui_router._try_handle_ui_message_legacy(client=client,message=message)
