"""WhatsApp channel-specific exception taxonomy."""


class WhatsAppError(Exception):
    """Base class for WhatsApp channel errors."""


class WhatsAppValidationError(WhatsAppError):
    """Raised when message content or state fails validation."""


class WhatsAppProviderError(WhatsAppError):
    """Raised when WhatsApp provider/network calls fail."""


class WhatsAppPersistenceError(WhatsAppError):
    """Raised when database/redis persistence operations fail."""


class WhatsAppFlowStateError(WhatsAppError):
    """Raised for domain rule and flow-state failures."""


class WhatsAppRateLimitError(WhatsAppProviderError):
    """Raised for rate-limiting backend failures or limits."""
