import re

from app.utils.logger import logger
from app.whatsapp.intents import INTENTS


HIGH_RISK_GENERIC_INTENTS = {"PAY", "REFUND", "SUMMARY", "HELP"}
_DISALLOWED_PREFIX_STARTERS = {
    "a",
    "an",
    "about",
    "can",
    "could",
    "for",
    "i",
    "me",
    "my",
    "please",
    "the",
    "to",
    "we",
    "with",
    "would",
    "you",
}


def _is_controlled_prefix_form(message: str, keyword: str) -> bool:
    if not message.startswith(keyword + " "):
        return False

    remainder = message[len(keyword) :].strip()
    if not remainder:
        return False

    if re.search(r"[.!?]", remainder):
        return False

    first_token = remainder.split()[0]
    if first_token in _DISALLOWED_PREFIX_STARTERS:
        return False

    return True


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
        if len(tokens) > 1 and tokens[1].isdigit() and allow_numeric_export_selection:
            logger.info("Intent detected by conversational export selection", extra={"intent": "EXPORT_SELECTION"})
            return "EXPORT_SELECTION"
        logger.info("Export prefix found but no numeric selection")
        return None

    if (
        msg.startswith("event ")
        and len(tokens) > 1
        and tokens[1].isdigit()
        and allow_numeric_export_selection
    ):
        logger.info("Intent detected by conversational event selection", extra={"intent": "EXPORT_SELECTION"})
        return "EXPORT_SELECTION"

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
        if intent in HIGH_RISK_GENERIC_INTENTS:
            if _is_controlled_prefix_form(msg, keyword):
                logger.info("Intent detected by controlled prefix", extra={"intent": intent})
                return intent
            continue

        if msg.startswith(keyword + " "):
            logger.info("Intent detected by startswith", extra={"intent": intent})
            return intent

    logger.info("No intent detected")
    return None
