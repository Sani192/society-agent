from app.utils.logger import logger
from app.whatsapp.intents import INTENTS


def detect_intent(message: str):
    msg = message.lower().strip()
    logger.info("Detecting intent", extra={"message_text": msg})

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
