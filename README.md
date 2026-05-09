#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Society Event Management Agent README

## 1. Overview
Society Event Management Agent is a FastAPI-based backend for managing society operations such as events, payments, sponsorships, expenses, refunds, and report exports.

### Architecture (channel layer vs domain modules)
- **Channel layer (`app/channels/*`, `app/whatsapp/*`)**
  - Handles transport-specific concerns (WhatsApp/Telegram request parsing, channel adapters, response formatting, webhook protocol handling).
  - Should stay thin and delegate business behavior to domain services.
- **Domain modules (`app/modules/*`)**
  - Implement core business logic (contributions, reports, reminders, refunds, participation, etc.).
  - Are channel-agnostic and reusable across interfaces.

### Multi-lingual Support
- **Native Localization**: Full support for English, Hindi, and Gujarati.
- **Cross-Language Robustness**: Understands native keywords regardless of active language setting.
- **Centralized Catalog**: Managed via `app/i18n/catalog.py`.

### Announcement architecture
- Detailed design and flow: `docs/announcements.md`

## 2. Prerequisites
- Python **3.10+**
- PostgreSQL **13+**
- `pip` (and recommended: `venv`)
- Optional: OpenAI API key when AI features are enabled

## 3. Environment variables
1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Update values as needed.

### Required
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

### Application/runtime
- `APP_ENV` (default: `local`)
- `TIMEZONE` (default: `Asia/Kolkata`)
- `CURRENCY_SYMBOL` (default: `₹`)
- `DEFAULT_SOCIETY_NAME`
- `ADMIN_PHONE_WHITELIST` (comma-separated phone numbers)
- `SCHEDULER_ENABLED` (default: `true`)

### AI (optional)
- `AI_ENABLED` (`true`/`false`)
- `AI_PROVIDER` (example: `openai`)
- `OPENAI_API_KEY`

### WhatsApp (optional)
- `WHATSAPP_MODE` (example: `SIMULATOR`)
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_API_VERSION` (example: `v22.0`)
- `WHATSAPP_GRAPH_BASE_URL` (default: `https://graph.facebook.com`)

### Telegram (optional)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_API_BASE_URL` (default: `https://api.telegram.org`)
- `TELEGRAM_WEBHOOK_SECRET`

## 4. DB setup/migrations
### Initial setup
1. Create DB user and database:
   ```sql
   CREATE USER society_user WITH PASSWORD 'society_pass';
   CREATE DATABASE society_db OWNER society_user;
   GRANT ALL PRIVILEGES ON DATABASE society_db TO society_user;
   ```
2. Ensure `.env` points to those credentials.
3. Start the application. Alembic will automatically run schema migrations at startup to create all tables.
   Alternatively, you can run migrations manually via:
   ```bash
   alembic upgrade head
   ```

### Bootstrap Seeding
Use bootstrap seeding to initialize baseline records (society, chairman, chairman channel identity, flats, periodic tasks) in a single guarded transaction.

1. Run command:
   ```bash
   python scripts/bootstrap_seed.py
   ```

2. One-time behavior and guard semantics:
   - Script acquires a PostgreSQL advisory transaction lock to prevent concurrent bootstrap runs.
   - It checks `bootstrap_seed_guard` for `seed_key='initial_bootstrap'`.
   - If the guard row already exists, the script logs the guard check result, prints `already seeded`, rolls back the current transaction context, and exits successfully (`0`).
   - On first successful run, it inserts the guard row and commits.

3. Transaction behavior (all-or-nothing rollback):
   - All bootstrap stages run in one DB transaction.
   - Any exception in any stage triggers `db.rollback()`.
   - Result: either everything is committed (including guard row) or nothing is persisted.

4. Config file schema (`bootstrap.seed.json`):
   - Default lookup: `./bootstrap.seed.json` (optional by default).
   - If present, it is validated strictly.
   - Required top-level structure:
     - `society`: `name`, `city`, `state`, `timezone` (all non-empty strings)
     - `onboarding`: `join_code` (string), `approval_required` (optional boolean)
     - `chairman`: `name`, `phone`, `channel_identity.external_user_id` (strings), optional `channel_identity.channel_type` (default `whatsapp`), optional `channel_identity.username`
     - `flats`: non-empty array of `{flat_number, block, owner_name}` (strings)
     - `periodic_task_defaults`: `enabled` (optional boolean), `run_hour` (`0..23`), `run_minute` (`0..59`)

## 5. Run instructions
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run API server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Run scheduler worker (separate process):
   ```bash
   python scripts/run_scheduler.py
   ```

## 6. API endpoints
### Core
- `GET /health` — service health check

### Channel webhooks
- `POST /whatsapp` — WhatsApp webhook (enabled when WhatsApp config is active)
- `POST /telegram` — Telegram webhook (enabled when Telegram config is active)

### Reports
- `GET /reports/financial/event-summary`
- `GET /reports/financial/flat-payments`
- `GET /reports/admin/members/export`
- `GET /reports/admin/onboarding/export`
- `GET /reports/governance/audit/export`
- `GET /reports/public/event-summary/pdf`

## 7. Testing/development commands
- Lint: `ruff check .`
- Fast unit tests: `pytest -m "not integration and not endpoint and not smoke"`
- Integration tests: `pytest -m "integration or endpoint"`
- Smoke tests: `pytest -m smoke`
- Combinatorial Localization tests: `pytest tests/e2e/test_combinatorial_matrix.py`