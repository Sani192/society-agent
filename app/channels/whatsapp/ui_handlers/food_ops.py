from app.channels.whatsapp import ui_router
CMDS={"verify food token","scan food qr","token status","serve flat","flat passes"}
PFX=(ui_router.FOOD_VERIFY_TOKEN_ROW_PREFIX,ui_router.FOOD_SCAN_QR_ROW_PREFIX,ui_router.FOOD_TOKEN_STATUS_ROW_PREFIX,ui_router.FOOD_SERVE_FLAT_ROW_PREFIX,ui_router.FOOD_FLAT_STATUS_ROW_PREFIX)
def can_handle(msg:str)->bool:return msg in CMDS or any(msg.startswith(p) for p in PFX)
def handle(*,client,message,context)->bool:return ui_router._try_handle_ui_message_legacy(client=client,message=message)
