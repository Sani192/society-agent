import re
from difflib import SequenceMatcher

from app.utils.logger import logger
from app.utils.operational_metrics import increment_counter
from app.modules.users.language_service import DEFAULT_LANGUAGE, normalize_language_code
from app.channels.whatsapp.intents import (
    INTENTS,
    INTENT_KEYWORDS_BY_LANGUAGE,
    SUPPORTED_INTENT_LANGUAGES,
)
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
    scored_candidates: list[tuple[float, str]] = []
    for candidate in candidates:
        ratio = SequenceMatcher(None, msg, candidate).ratio()
        candidate_best = ratio
        if ratio > best_ratio:
            best_ratio = ratio

        for word in words:
            token_ratio = SequenceMatcher(None, word, candidate).ratio()
            if token_ratio > candidate_best:
                candidate_best = token_ratio
            if token_ratio > best_ratio:
                best_ratio = token_ratio
        scored_candidates.append((candidate_best, candidate))

    if best_ratio < 0.72:
        return None

    suggestions: list[str] = []
    for _score, candidate in sorted(scored_candidates, key=lambda item: item[0], reverse=True):
        if candidate not in suggestions:
            suggestions.append(candidate)
        if len(suggestions) >= 3:
            break

    examples = ", ".join(
        [
            _localized_keywords_for_intent("JOIN", effective_language)[0],
            _localized_keywords_for_intent("PAY", effective_language)[0],
            _localized_keywords_for_intent("REFUND", effective_language)[0],
            _localized_keywords_for_intent("HELP", effective_language)[0],
        ]
    )
    did_you_mean = ", ".join(suggestions) if suggestions else examples
    language_name = _LANGUAGE_NAMES.get(effective_language, _LANGUAGE_NAMES[DEFAULT_LANGUAGE])
    return translate(
        "response_templates.near_match_hint",
        effective_language,
        message_text=msg,
        language_name=language_name,
        did_you_mean=did_you_mean,
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
    increment_counter("intent.detect.total")
    increment_counter(f"intent.detect.total.{effective_language}")
    logger.info("Detecting intent", extra={"message_text": msg})

    if msg.isdigit() and allow_numeric_export_selection:
        increment_counter("intent.detect.matched")
        increment_counter(f"intent.detect.matched.{effective_language}")
        logger.info("Intent detected by numeric conversational export selection", extra={"intent": "EXPORT_SELECTION"})
        return "EXPORT_SELECTION"

    if msg.startswith("export "):
        if len(tokens) > 1 and tokens[1].isdigit() and allow_numeric_export_selection:
            increment_counter("intent.detect.matched")
            increment_counter(f"intent.detect.matched.{effective_language}")
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
        increment_counter("intent.detect.matched")
        increment_counter(f"intent.detect.matched.{effective_language}")
        logger.info("Intent detected by conversational event selection", extra={"intent": "EXPORT_SELECTION"})
        return "EXPORT_SELECTION"

    if msg.startswith("export::"):
        increment_counter("intent.detect.matched")
        increment_counter(f"intent.detect.matched.{effective_language}")
        logger.info(
            "Intent detected by interactive export selection",
            extra={"intent": "EXPORT_SELECTION"},
        )
        return "EXPORT_SELECTION"

    for intent, keyword in _iter_intent_keywords(intent_map, language=effective_language):
        if msg == keyword:
            increment_counter("intent.detect.matched")
            increment_counter(f"intent.detect.matched.{effective_language}")
            increment_counter(f"intent.detect.intent.{intent}")
            increment_counter(f"intent.detect.intent.{intent}.{effective_language}")
            logger.info("Intent detected by exact match", extra={"intent": intent})
            return intent

    for intent, keyword in _iter_intent_keywords(intent_map, language=effective_language):
        if intent in HIGH_RISK_GENERIC_INTENTS:
            continue
        if msg.startswith(keyword + " "):
            increment_counter("intent.detect.matched")
            increment_counter(f"intent.detect.matched.{effective_language}")
            increment_counter(f"intent.detect.intent.{intent}")
            increment_counter(f"intent.detect.intent.{intent}.{effective_language}")
            logger.info("Intent detected by startswith", extra={"intent": intent})
            return intent

    for intent, keyword in _iter_intent_keywords(intent_map, language=effective_language):
        if intent not in HIGH_RISK_GENERIC_INTENTS:
            continue
        if _is_controlled_prefix_form(
            msg,
            keyword,
            disallowed_prefix_starters=disallowed_prefix_starters,
        ):
            increment_counter("intent.detect.matched")
            increment_counter(f"intent.detect.matched.{effective_language}")
            increment_counter(f"intent.detect.intent.{intent}")
            increment_counter(f"intent.detect.intent.{intent}.{effective_language}")
            logger.info("Intent detected by controlled prefix", extra={"intent": intent})
            return intent

    # ========= CROSS-LANGUAGE FALLBACK =========
    # If not found in effective language, check other supported languages
    other_languages = [l for l in SUPPORTED_INTENT_LANGUAGES if l != effective_language]
    for other_lang in other_languages:
        for intent, keyword in _iter_intent_keywords(intent_map, language=other_lang):
            if msg == keyword:
                increment_counter("intent.detect.matched.cross_lang")
                logger.info("Intent detected by cross-language exact match", extra={"intent": intent, "source_lang": other_lang})
                return intent
            if msg.startswith(keyword + " ") and intent not in HIGH_RISK_GENERIC_INTENTS:
                increment_counter("intent.detect.matched.cross_lang")
                logger.info("Intent detected by cross-language startswith", extra={"intent": intent, "source_lang": other_lang})
                return intent

    increment_counter("intent.detect.unmatched")
    increment_counter(f"intent.detect.unmatched.{effective_language}")
    logger.info("No intent detected")
    return None
