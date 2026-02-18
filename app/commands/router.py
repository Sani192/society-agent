from app.utils.logger import logger
from app.whatsapp.intents import INTENTS


def detect_intent(
    message: str,
    *,
    intents: dict[str, str] | None = None,
    allow_numeric_export_selection: bool = True,
):
    msg = message.lower().strip()
    tokens = msg.split()
    intent_map = intents or INTENTS
    logger.info("Detecting intent", extra={"message_text": msg})

    if msg.isdigit() and allow_numeric_export_selection:
        logger.info("Intent detected by numeric conversational export selection", extra={"intent": "EXPORT_SELECTION"})
        return "EXPORT_SELECTION"

    if msg.startswith("export "):
        if len(tokens) > 1 and tokens[1].isdigit():
            logger.info("Intent detected by conversational export selection", extra={"intent": "EXPORT_SELECTION"})
            return "EXPORT_SELECTION"
        logger.info("Export prefix found but no numeric selection")
        return None



    if msg == "reports":
        logger.info("Legacy reports alias unsupported; use report options")
        return None

    if msg.startswith("report export"):
        logger.info(
            "Legacy report export free-text is unsupported; use report options",
        )
        return None

    if msg.startswith("export::"):
        logger.info(
            "Intent detected by interactive export selection",
            extra={"intent": "EXPORT_SELECTION"},
        )
        return "EXPORT_SELECTION"

    for intent, keyword in intent_map.items():
        if msg == keyword:
            logger.info("Intent detected by exact match", extra={"intent": intent})
            return intent

    for intent, keyword in intent_map.items():
        if msg.startswith(keyword + " "):
            logger.info("Intent detected by startswith", extra={"intent": intent})
            return intent

    for intent, keyword in intent_map.items():
        if f" {keyword} " in f" {msg} ":
            logger.info("Intent detected by word-boundary", extra={"intent": intent})
            return intent

    logger.info("No intent detected")
    return None
