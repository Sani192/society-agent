from app.utils.logger import logger
from app.whatsapp.intents import INTENTS


def detect_intent(message: str):
    msg = message.lower().strip()
    tokens = msg.split()
    logger.info("Detecting intent", extra={"message_text": msg})

    if msg.startswith("export "):
        if len(tokens) > 1 and tokens[1].isdigit():
            logger.info("Intent detected by conversational export selection", extra={"intent": "EXPORT_SELECTION"})
            return "EXPORT_SELECTION"
        logger.info("Export prefix found but no numeric selection")
        return None

    for intent, keyword in INTENTS.items():
        if msg == keyword:
            logger.info("Intent detected by exact match", extra={"intent": intent})
            return intent

    for intent, keyword in INTENTS.items():
        if msg.startswith(keyword + " "):
            logger.info("Intent detected by startswith", extra={"intent": intent})
            return intent

    for intent, keyword in INTENTS.items():
        if f" {keyword} " in f" {msg} ":
            logger.info("Intent detected by word-boundary", extra={"intent": intent})
            return intent

    logger.info("No intent detected")
    return None
