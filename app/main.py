#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:47:02 2026

@author: anonymous
"""

# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.base import Base
from app.db.session import engine
from app.db.session import SessionLocal
from app.db.models import Society
from app.utils.logger import logger
from app.config import settings


from app.api.contracts import API_SCHEMA_VERSION
from app.api.health import router as health_router
from app.api.whatsapp import router as whatsapp_router
from app.api.telegram import router as telegram_router
from app.api.reports.financial import router as financial_reports_router
from app.api.reports.administrative import router as administrative_reports_router
from app.api.reports.governance import router as governance_reports_router
from app.api.reports.public import router as public_reports_router
from app.api.reports.operations import router as operations_reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    # Startup sanity checks
    db = SessionLocal()
    try:
        society = db.query(Society).first()
        if not society:
            logger.warning("No society found in database")
        else:
            logger.info(f"Loaded society: {society.name}")

    finally:
        db.close()

    yield
    logger.info("Society Agent shutting down")
    # Shutdown (nothing for now)



app = FastAPI(
    title="Society Event Management Agent",
    version=API_SCHEMA_VERSION,
    lifespan=lifespan
)

# Routes
app.include_router(health_router)
if settings.WHATSAPP_ENABLED:
    app.include_router(whatsapp_router)

if settings.TELEGRAM_ENABLED:
    app.include_router(telegram_router)
app.include_router(financial_reports_router)
app.include_router(administrative_reports_router)
app.include_router(governance_reports_router)
app.include_router(public_reports_router)
app.include_router(operations_reports_router)
