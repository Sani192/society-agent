#!/usr/bin/env python3

import re


def normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or value.strip()
