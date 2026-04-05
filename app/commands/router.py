import re
from difflib import SequenceMatcher

from app.utils.logger import logger
from app.modules.users.language_service import DEFAULT_LANGUAGE, normalize_language_code
from app.channels.whatsapp.intents import INTENTS, INTENT_KEYWORDS_BY_LANGUAGE
from app.i18n.catalog import translate


HIGH_RISK_GENERIC_INTENTS = {"PAY", "REFUND", "SUMMARY", "HELP"}
_DISALLOWED_PREFIX_STARTERS_BY_LANGUAGE = {
    "en": {
        "a", "an", "about", "can", "could", "for", "i", "me", "my", "please", "the", "to", "we", "with", "would", "you",
    },
    "hi": {
        "का", "के", "की", "कृपया", "क्या", "तुम", "तुम्हारा", "मैं", "मुझे", "मेरे", "हम", "हमें", "हमारा",
    },
    "gu": {
        "કૃપા", "કૃપા કરીને", "શું", "તમે", "તમારું", "હું", "મને", "મારું", "અમે", "અમને", "અમારું",
    },
}
_LANGUAGE_NAMES = {"en": "English", "hi": "हिंदी", "gu": "ગુજરાતી"}
_NEAR_MATCH_INTENTS = (
    "JOIN",
    "JOIN_STATUS",
    "PAY",
    "REFUND",
    "ADD_PASS",
    "MENU",
    "HELP",
    "REPORT_OPTIONS",
    "SUMMARY",
    "APPROVE_PAYMENT",
    "APPROVE_REFUND",
    "APPROVE",
    "LIST_COMMITTEE_MEMBERS",
    "ADD_COMMITTEE_MEMBER",
    "REMOVE_COMMITTEE_MEMBER",
    "CHANGE_COMMITTEE_ROLE",
)


def _get_effective_language(language: str | None) -> str:
    return normalize_language_code(language) or DEFAULT_LANGUAGE


def _get_disallowed_prefix_starters(language: str | None) -> set[str]:
    effective_language = _get_effective_language(language)
    localized_starters = _DISALLOWED_PREFIX_STARTERS_BY_LANGUAGE.get(effective_language, set())
    return set(_DISALLOWED_PREFIX_STARTERS_BY_LANGUAGE[DEFAULT_LANGUAGE]) | set(localized_starters)


def _is_controlled_prefix_form(message: str, keyword: str, *, disallowed_prefix_starters: set[str]) -> bool:
    if not message.startswith(keyword + " "):
        return False

    remainder = message[len(keyword) :].strip()
    if not remainder:
        return False

    if re.search(r"[.!?]", remainder):
        return False

    first_token = remainder.split()[0]
    if first_token in disallowed_prefix_starters:
        return False

    return True


def _localized_keywords_for_intent(intent: str, language: str) -> list[str]:
    keyword_sets = INTENT_KEYWORDS_BY_LANGUAGE.get(intent, {})
    localized = list(keyword_sets.get(language) or [])
    english = list(keyword_sets.get(DEFAULT_LANGUAGE) or [])
    ordered: list[str] = []
    for keyword in [*localized, *english]:
        keyword = keyword.strip().lower()
        if keyword and keyword not in ordered:
            ordered.append(keyword)
    return ordered


def _iter_intent_keywords(intent_map: dict[str, str], *, language: str):
    for intent, fallback_keyword in intent_map.items():
        localized_keywords = _localized_keywords_for_intent(intent, language)
        if localized_keywords:
            for keyword in localized_keywords:
                yield intent, keyword
            continue
        yield intent, fallback_keyword.strip().lower()


def _normalized_words(message: str) -> list[str]:
    return [token for token in re.split(r"\s+", message.strip().lower()) if token]


def localized_near_match_feedback(message: str, *, language: str | None = None) -> str | None:
    effective_language = _get_effective_language(language)
    msg = message.strip().lower()
    if not msg or len(msg) < 3:
        return None

    candidates: list[str] = []
    for intent in _NEAR_MATCH_INTENTS:
        candidates.extend(_localized_keywords_for_intent(intent, effective_language))
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return None

    words = _normalized_words(msg)
    best_ratio = 0.0
    best_candidate = ""

    for candidate in candidates:
        ratio = SequenceMatcher(None, msg, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = candidate

        for word in words:
            token_ratio = SequenceMatcher(None, word, candidate).ratio()
            if token_ratio > best_ratio:
                best_ratio = token_ratio
                best_candidate = candidate

    if best_ratio < 0.72:
        return None

    examples = ", ".join(
        [
            _localized_keywords_for_intent("JOIN", effective_language)[0],
            _localized_keywords_for_intent("PAY", effective_language)[0],
            _localized_keywords_for_intent("REFUND", effective_language)[0],
            _localized_keywords_for_intent("HELP", effective_language)[0],
        ]
    )
    language_name = _LANGUAGE_NAMES.get(effective_language, _LANGUAGE_NAMES[DEFAULT_LANGUAGE])
    return translate(
        "response_templates.near_match_hint",
        effective_language,
        message_text=msg,
        language_name=language_name,
        localized_examples=examples,
    )


def detect_intent(
    message: str,
    *,
    intents: dict[str, str] | None = None,
    language: str | None = None,
    allow_numeric_export_selection: bool = True,
):
    msg = message.lower().strip()
    tokens = msg.split()
    intent_map = intents or INTENTS
    effective_language = _get_effective_language(language)
    disallowed_prefix_starters = _get_disallowed_prefix_starters(effective_language)
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

    if msg.startswith("export::"):
        logger.info(
            "Intent detected by interactive export selection",
            extra={"intent": "EXPORT_SELECTION"},
        )
        return "EXPORT_SELECTION"

    for intent, keyword in _iter_intent_keywords(intent_map, language=effective_language):
        if msg == keyword:
            logger.info("Intent detected by exact match", extra={"intent": intent})
            return intent

    for intent, keyword in _iter_intent_keywords(intent_map, language=effective_language):
        if intent in HIGH_RISK_GENERIC_INTENTS:
            if _is_controlled_prefix_form(
                msg,
                keyword,
                disallowed_prefix_starters=disallowed_prefix_starters,
            ):
                logger.info("Intent detected by controlled prefix", extra={"intent": intent})
                return intent
            continue

        if msg.startswith(keyword + " "):
            logger.info("Intent detected by startswith", extra={"intent": intent})
            return intent

    logger.info("No intent detected")
    return None
