#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:08:02 2026

@author: anonymous
"""

from app.whatsapp.handler import handle_message
from app.db.models import CommitteeMember
from app.db.session import SessionLocal

def run():
    db = SessionLocal()
    member = db.query(CommitteeMember).first()
    db.close()

    phone = member.phone_number

    print(handle_message(phone, "add pass"))
    print(handle_message(phone, "pay"))
    print(handle_message(phone, "refund"))
    print(handle_message(phone, "expense"))
    print(handle_message(phone, "summary"))

if __name__ == "__main__":
    run()
