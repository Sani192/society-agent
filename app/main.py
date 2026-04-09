#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:47:02 2026

@author: anonymous
"""

# app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from app.db.base import Base
from app.db.models import Society
from app.db.session import SessionLocal
from app.db.session import engine
from app.utils.logger import logger
from app.config import settings
from app.channels.whatsapp.config_validation import validate_whatsapp_runtime_config
from app.utils.operational_metrics import increment_counter

from app.api.contracts import API_SCHEMA_VERSION
from app.api.health import router as health_router
from app.api.whatsapp import router as whatsapp_router
from app.api.telegram import router as telegram_router
from app.api.reports.financial import router as financial_reports_router
from app.api.reports.administrative import router as administrative_reports_router
from app.api.reports.governance import router as governance_reports_router
from app.api.reports.public import router as public_reports_router
from app.api.reports.operations import router as operations_reports_router


class PublicRequestSizeGuardMiddleware(BaseHTTPMiddleware):
    """Apply global request-size limits for unauthenticated/public API paths."""

    _PUBLIC_ENDPOINT_PREFIXES = ("/health", "/whatsapp", "/telegram", "/reports/public")
    _BODY_METHODS = {"POST", "PUT", "PATCH"}

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() in self._BODY_METHODS and request.url.path.startswith(self._PUBLIC_ENDPOINT_PREFIXES):
            max_body_bytes = max(1024, int(settings.PUBLIC_ENDPOINT_MAX_BODY_BYTES))
            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > max_body_bytes:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

            raw_body = await request.body()
            if len(raw_body) > max_body_bytes:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

            async def receive() -> Message:
                return {"type": "http.request", "body": raw_body, "more_body": False}

            request._receive = receive

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline response security headers for API responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
        if _request_is_https(request):
            # HSTS is applied only when the request arrives over HTTPS. In production
            # TLS is typically terminated by a reverse proxy and forwarded via headers.
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def _request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True

    x_forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if x_forwarded_proto:
        proto = x_forwarded_proto.split(",", 1)[0].strip().lower()
        if proto == "https":
            return True

    x_forwarded_scheme = request.headers.get("x-forwarded-scheme", "")
    if x_forwarded_scheme and x_forwarded_scheme.strip().lower() == "https":
        return True

    forwarded = request.headers.get("forwarded", "")
    if "proto=https" in forwarded.replace(" ", "").lower():
        return True

    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    # Startup sanity checks
    if settings.WHATSAPP_ENABLED:
        validation = validate_whatsapp_runtime_config()
        if validation.complete:
            logger.info("WhatsApp startup config validation passed")
        else:
            increment_counter("whatsapp.config.validation_failure")
            logger.error(
                "WhatsApp startup config validation failed",
                extra={
                    "event": "whatsapp_config_validation_failure",
                    "context": "startup",
                    "missing_fields": list(validation.missing_fields),
                },
            )

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
    lifespan=lifespan,
)

if settings.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        max_age=600,
    )

app.add_middleware(PublicRequestSizeGuardMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

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
