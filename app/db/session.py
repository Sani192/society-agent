#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 10 13:22:03 2026

@author: anonymous
"""

# app/db/session.py

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.utils.logger import logger

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def _resolve_database_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL

    if all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        return (
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )

    if settings.APP_ENV_NORMALIZED in {"local", "dev"}:
        return "sqlite:///./society_agent.db"

    raise RuntimeError(
        "DATABASE_URL is required when APP_ENV is staging/production or non-local environment"
    )


def _build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, object] = {}

    if url.drivername.startswith("postgresql"):
        connect_args["options"] = f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"

    return create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args=connect_args,
    )


def _backend_label(database_url: str) -> str:
    drivername = make_url(database_url).drivername
    return drivername.split("+", maxsplit=1)[0]


def _log_db_diagnostics(primary_url: str, read_replica_url: str | None) -> None:
    logger.info(
        "Database configuration loaded",
        extra={
            "app_env": settings.APP_ENV,
            "primary_backend": _backend_label(primary_url),
            "read_replica_enabled": bool(read_replica_url),
            "read_replica_backend": _backend_label(read_replica_url) if read_replica_url else None,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "statement_timeout_ms": settings.DB_STATEMENT_TIMEOUT_MS,
        },
    )


DATABASE_URL = _resolve_database_url()
READ_REPLICA_DATABASE_URL = settings.READ_REPLICA_DATABASE_URL

engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

read_engine = None
ReadSessionLocal = None
if READ_REPLICA_DATABASE_URL:
    read_engine = _build_engine(READ_REPLICA_DATABASE_URL)
    ReadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=read_engine)

_log_db_diagnostics(DATABASE_URL, READ_REPLICA_DATABASE_URL)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db():
    session_factory = ReadSessionLocal or SessionLocal
    db = session_factory()
    try:
        if read_engine and make_url(READ_REPLICA_DATABASE_URL).drivername.startswith("postgresql"):
            db.execute(text("SET TRANSACTION READ ONLY"))
        yield db
    finally:
        db.close()
