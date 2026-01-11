#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:32:11 2026

@author: anonymous
"""

# app/api/whatsapp.py

from fastapi import APIRouter
from pydantic import BaseModel

from app.whatsapp.handler import handle_message

router = APIRouter()


class WhatsAppRequest(BaseModel):
    phone_number: str
    message: str


@router.post("/whatsapp")
def whatsapp_webhook(payload: WhatsAppRequest):
    response = handle_message(
        phone_number=payload.phone_number,
        message=payload.message
    )
    return {
        "reply": response
    }
