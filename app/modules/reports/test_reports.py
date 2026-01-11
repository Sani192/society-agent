#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:58:26 2026

@author: anonymous
"""

from app.db.session import SessionLocal
from app.db.models import Event
from app.modules.reports.event_summary import EventSummaryReport
from app.modules.reports.block_wise import BlockWiseReport
from app.modules.reports.sponsor_wise import SponsorWiseReport
from app.modules.reports.override_report import OverrideReport

def run():
    db = SessionLocal()
    event = db.query(Event).first()

    print("📊 EVENT SUMMARY")
    print(EventSummaryReport.generate(db=db, event_id=event.id))

    print("\n🏢 BLOCK-WISE")
    print(BlockWiseReport.generate(db=db, event_id=event.id))

    print("\n🤝 SPONSORS")
    print(SponsorWiseReport.generate(db=db, event_id=event.id))

    print("\n⚠️ OVERRIDES")
    print(OverrideReport.generate(db=db, event_id=event.id))

    db.close()

if __name__ == "__main__":
    run()
