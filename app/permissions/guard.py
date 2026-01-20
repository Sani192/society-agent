#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:56:55 2026

@author: anonymous
"""

# app/permissions/guard.py

from app.permissions.roles import ROLE_ACTIONS


def is_action_allowed(role: str, action: str) -> bool:
    allowed = ROLE_ACTIONS.get(role, set())
    return "ALL" in allowed or action in allowed
