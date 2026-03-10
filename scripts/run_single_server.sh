#!/usr/bin/env bash
set -euo pipefail

# Single-host launcher:
# - Starts scheduler worker in background
# - Starts API server in foreground
# - Ensures scheduler stops when API exits

cleanup() {
  if [[ -n "${SCHEDULER_PID:-}" ]] && kill -0 "$SCHEDULER_PID" 2>/dev/null; then
    kill "$SCHEDULER_PID" 2>/dev/null || true
    wait "$SCHEDULER_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

python scripts/run_scheduler.py &
SCHEDULER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port 8000
