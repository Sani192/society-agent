#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:27:21 2026

@author: anonymous
"""

# app/utils/response.py

def success(message: str):
    return f"✅ {message}"


def warning(message: str):
    return f"⚠️ {message}"


def error(message: str):
    return f"❌ {message}"


def error_envelope(message: str):
    return {
        "status": "error",
        "message": message
    }


def info(message: str):
    return f"ℹ️ {message}"
