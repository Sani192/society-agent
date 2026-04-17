#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:47:02 2026

@author: anonymous
"""

# app/main.py

from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy import text

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

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "docs" / "migrations"


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




def _pending_schema_differences() -> tuple[list[str], dict[str, list[str]]]:
    inspector = inspect(engine)
    expected_tables = set(Base.metadata.tables.keys())
    inspected_tables = set(inspector.get_table_names())
    missing_tables = sorted(expected_tables - inspected_tables)

    missing_columns_by_table: dict[str, list[str]] = {}
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspected_tables:
            continue
        inspected_columns = {column["name"] for column in inspector.get_columns(table_name)}
        model_columns = {column.name for column in table.columns}
        missing_columns = sorted(model_columns - inspected_columns)
        if missing_columns:
            missing_columns_by_table[table_name] = missing_columns

    return missing_tables, missing_columns_by_table


def _migration_file_paths() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(path for path in MIGRATIONS_DIR.iterdir() if path.is_file() and path.suffix == ".sql")


def _ensure_migration_tracking_table() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def _applied_migrations() -> set[str]:
    _ensure_migration_tracking_table()
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT filename FROM schema_migrations")).fetchall()
    return {row[0] for row in rows}


def _apply_migration_file(migration_file: Path) -> None:
    sql_script = migration_file.read_text(encoding="utf-8")
    if not sql_script.strip():
        return

    raw_connection = engine.raw_connection()
    try:
        cursor = raw_connection.cursor()
        try:
            if hasattr(cursor, "executescript"):
                cursor.executescript(sql_script)
            else:
                cursor.execute(sql_script)
            raw_connection.commit()
        finally:
            cursor.close()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        raw_connection.close()


def _run_migration_pipeline() -> None:
    applied = _applied_migrations()
    for migration_file in _migration_file_paths():
        migration_name = migration_file.name
        if migration_name in applied:
            continue
        _apply_migration_file(migration_file)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:filename)"),
                {"filename": migration_name},
            )


def _app_env_normalized() -> str:
    configured_env = getattr(settings, "APP_ENV_NORMALIZED", None)
    if isinstance(configured_env, str) and configured_env.strip():
        return configured_env.strip().lower()
    return str(getattr(settings, "APP_ENV", "local")).strip().lower()


def _enforce_schema_readiness() -> None:
    app_env_normalized = _app_env_normalized()
    if app_env_normalized in {"local", "dev"}:
        Base.metadata.create_all(bind=engine)
        return

    if app_env_normalized in {"staging", "production"}:
        if settings.STARTUP_MIGRATIONS_ENABLED:
            _run_migration_pipeline()
        pending_tables, missing_columns_by_table = _pending_schema_differences()
        if pending_tables or missing_columns_by_table:
            pending_tables_csv = ", ".join(pending_tables) if pending_tables else "none"
            missing_columns_summary = (
                "; ".join(
                    f"{table_name}: {', '.join(columns)}"
                    for table_name, columns in sorted(missing_columns_by_table.items())
                )
                if missing_columns_by_table
                else "none"
            )
            raise RuntimeError(
                "Pending database migrations detected in "
                f"APP_ENV={getattr(settings, 'APP_ENV', app_env_normalized)}. "
                f"Missing tables: {pending_tables_csv}. "
                f"Missing columns: {missing_columns_summary}. "
                "Run the migration pipeline before starting the application "
                "(or set STARTUP_MIGRATIONS_ENABLED=true for controlled startup automation)."
            )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _enforce_schema_readiness()

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
