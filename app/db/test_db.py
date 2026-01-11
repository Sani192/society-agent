#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:25:02 2026

@author: anonymous
"""

# test_db.py  (temporary)

from app.db.session import engine

def test_connection():
    with engine.connect() as conn:
        print("✅ Database connection successful")

if __name__ == "__main__":
    test_connection()