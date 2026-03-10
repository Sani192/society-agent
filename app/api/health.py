#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:31:26 2026

@author: anonymous
"""

# app/api/health.py

from fastapi import APIRouter

from app.api.contracts import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", message="Society Agent running locally")
