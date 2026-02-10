from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    channel: str
    sender_id: str
    display_name: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
