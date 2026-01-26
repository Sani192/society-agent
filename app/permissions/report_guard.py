#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 12:02:07 2026

@author: anonymous
"""

from app.permissions.report_permissions import REPORT_PERMISSIONS

def ensure_report_access(role: str, report_code: str):
    allowed_roles = REPORT_PERMISSIONS.get(report_code)

    if not allowed_roles:
        raise Exception("Invalid report")

    if role not in allowed_roles:
        raise Exception("You are not allowed to access this report")
