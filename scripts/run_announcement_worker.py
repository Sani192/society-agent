#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""RQ worker entrypoint for durable announcement delivery tasks."""

from __future__ import annotations

import multiprocessing
import signal
import time

import redis
from rq import Connection, Worker

from app.config import settings
from app.utils.logger import logger

_running = True
_workers: list[multiprocessing.Process] = []


def _handle_signal(signum, _frame):
    global _running
    logger.info("Announcement worker received shutdown signal", extra={"signal": signum})
    _running = False


def _run_single_worker(queue_name: str) -> None:
    conn = redis.from_url(settings.REDIS_URL)
    with Connection(conn):
        worker = Worker([queue_name])
        worker.work(with_scheduler=True)


def _spawn_workers(queue_name: str, count: int) -> None:
    for _ in range(max(count, 1)):
        process = multiprocessing.Process(target=_run_single_worker, args=(queue_name,), daemon=True)
        process.start()
        _workers.append(process)


def main() -> int:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    _spawn_workers(settings.ANNOUNCEMENT_QUEUE_WHATSAPP, settings.ANNOUNCEMENT_WORKER_CONCURRENCY_WHATSAPP)
    _spawn_workers(settings.ANNOUNCEMENT_QUEUE_DEFAULT, settings.ANNOUNCEMENT_WORKER_CONCURRENCY_DEFAULT)

    logger.info(
        "Announcement worker started",
        extra={
            "redis_url": settings.REDIS_URL,
            "whatsapp_queue": settings.ANNOUNCEMENT_QUEUE_WHATSAPP,
            "default_queue": settings.ANNOUNCEMENT_QUEUE_DEFAULT,
            "whatsapp_concurrency": settings.ANNOUNCEMENT_WORKER_CONCURRENCY_WHATSAPP,
            "default_concurrency": settings.ANNOUNCEMENT_WORKER_CONCURRENCY_DEFAULT,
        },
    )

    while _running:
        alive = [proc for proc in _workers if proc.is_alive()]
        if not alive:
            logger.error("All announcement worker processes exited")
            return 1
        time.sleep(1)

    for proc in _workers:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)

    logger.info("Announcement worker shutting down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
