#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 12:01:17 2026

@author: anonymous
"""

REPORT_PERMISSIONS = {
    # committee_member intentionally excluded from exports by default

    "GOVERNANCE_AUDIT": {"chairman"},
    "EVENT_FINANCIAL_SUMMARY": {"chairman", "treasurer"},
    "FLAT_PAYMENTS": {"chairman", "treasurer"},
    "BLOCK_PAYMENTS": {"chairman", "treasurer"},
    "SPONSOR_CONTRIBUTIONS": {"chairman", "treasurer"},
    "CONTRIBUTION_REFUNDS": {"chairman", "treasurer"},
    "BALANCE_CONTINUITY": {"chairman", "treasurer"},
    "MEMBER_REFUNDS": {"chairman", "treasurer"},
    "MEMBER_DIRECTORY": {"chairman", "secretary"},
    "ONBOARDING_STATUS": {"chairman", "secretary"},
    "ANNOUNCEMENT_HISTORY": {"chairman", "secretary"},
    "LEDGER": {"chairman", "secretary", "treasurer"}
}
