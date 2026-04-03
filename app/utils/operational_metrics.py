#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight in-process operational counters."""

from __future__ import annotations

from collections import Counter

_COUNTERS: Counter[str] = Counter()


def increment_counter(name: str, amount: int = 1) -> None:
    if amount <= 0:
        return
    _COUNTERS[name] += int(amount)


def get_counter(name: str) -> int:
    return int(_COUNTERS.get(name, 0))


def snapshot_counters() -> dict[str, int]:
    return {key: int(value) for key, value in _COUNTERS.items()}


def reset_counters() -> None:
    _COUNTERS.clear()
