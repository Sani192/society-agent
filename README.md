# Society Event Management Agent

> FastAPI backend for housing-society operations across WhatsApp, Telegram, HTTP report APIs, scheduler workers, and domain services.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#prerequisites)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128-teal.svg)](#run-the-api)
[![Database](https://img.shields.io/badge/database-PostgreSQL%20%7C%20local%20SQLite-lightgrey.svg)](#database--migrations)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](#testing)

---

## Table of contents

- [What this project does](#what-this-project-does)
- [Feature map](#feature-map)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Database & migrations](#database--migrations)
- [Running services](#running-services)
- [API surface](#api-surface)
- [Messaging commands](#messaging-commands)
- [Reports](#reports)
- [Operational scripts](#operational-scripts)
- [Testing](#testing)
- [Documentation map](#documentation-map)

---

## What this project does

Society Event Management Agent helps a housing society run event and finance operations from chat channels and APIs. It supports:

- **Member onboarding** with join codes, approval flows, channel identities, and phone verification.
- **Event lifecycle management** from draft creation to active, locked, event-day, and closed states.
- **Payments, refunds, sponsor contributions, expenses, and ledger continuity**.
- **Food pass and token operations** for event-day counters.
- **Committee administration** including committee member management and role-aware command access.
- **Announcements** with asynchronous, template-safe delivery.
- **Financial, operational, administrative, governance, and public reports**.
- **Multilingual WhatsApp UX** in English, Hindi, and Gujarati with cross-language command fallback.
- **Webhook reliability** with signature checks, idempotency, retry queues, rate limits, audit events, and dead-letter records.

---

## Feature map

| Area | Current capabilities | Main code paths |
|---|---|---|
| Channels | WhatsApp and Telegram webhook ingestion, adapters, clients, shared inbound handler | `app/api/whatsapp/webhook.py`, `app/api/telegram.py`, `app/channels/*` |
| Commands | Intent detection, localized command keywords, command routing, role/state policy | `app/commands/*`, `app/channels/whatsapp/intents.py`, `app/permissions/*` |
| Onboarding | Join requests, pending-user approval, link codes, phone challenges, user-flat mapping | `app/modules/onboarding/*`, `app/modules/users/*` |
| Events | Event creation/session flows, pass booking, food token generation, food serving | `app/modules/events/*`, `app/channels/whatsapp/*event*`, `app/channels/whatsapp/ui_handlers/food_ops.py` |
| Finance | Payments, payment requests, refunds, refund requests, sponsors, expenses, ledger | `app/modules/payments/*`, `app/modules/contributions/*`, `app/modules/expenses/*`, `app/modules/ledger/*` |
| Committee | Committee member CRUD, role changes, identity resolution, approvals | `app/modules/committee/*`, `app/channels/whatsapp/committee_*` |
| Announcements | Recipient resolution, queued deliveries, retries, RQ/local dispatch backends | `app/modules/announcements/*`, `scripts/run_announcement_worker.py` |
| Reports | HTTP exports and WhatsApp report selection/export sessions | `app/api/reports/*`, `app/modules/reports/*`, `app/channels/whatsapp/report_flow.py` |
| Scheduler | Dedicated scheduler worker with periodic task synchronization | `app/modules/scheduler/*`, `scripts/run_scheduler.py` |
| Audit & security | Channel audit events, governance exports, retention pruning, security logging | `app/channels/core/audit_*`, `app/modules/audit/*`, `app/api/reports/governance.py` |

---

## Architecture

```text
External channels / clients
        │
        ▼
FastAPI entrypoints
  ├─ /whatsapp webhook
  ├─ /telegram webhook
  ├─ /health and readiness
  └─ /reports/* APIs
        │
        ▼
Channel layer
  ├─ parse provider payloads
  ├─ verify signatures/secrets
  ├─ normalize inbound messages
  ├─ persist audit + reliability envelopes
  └─ send provider-specific replies/documents
        │
        ▼
Command + workflow layer
  ├─ localized intent detection
  ├─ role and event-state guards
  ├─ WhatsApp sessions/UI flows
  └─ shared inbound handler
        │
        ▼
Domain modules
  ├─ events / food passes
  ├─ payments / refunds / contributions / expenses / ledger
  ├─ onboarding / users / committee
  ├─ announcements / reminders / scheduler
  └─ reports / audit / security
        │
        ▼
Database
  ├─ Alembic-managed schema
  ├─ PostgreSQL for deployed environments
  └─ SQLite fallback for local/dev when DB env is absent
```

### Design principles

- **Channel layer stays thin**: WhatsApp and Telegram code handles transport, parsing, formatting, and provider concerns.
- **Domain services own business logic**: reusable service modules under `app/modules/*` are channel-agnostic.
- **Policies are explicit**: role and event-state behavior is centralized in `app/permissions/*` and covered by tests.
- **Operational behavior is auditable**: webhook envelopes, channel messages, audit events, retries, and governance reports are first-class.

---

## Repository layout

```text
app/
  api/                 FastAPI routes: health, channel webhooks, reports
  channels/            WhatsApp, Telegram, and shared channel runtime
  commands/            Intent parser/router and command handlers
  db/                  SQLAlchemy models, sessions, database base
  modules/             Business/domain services
  permissions/         Role, report, and command access policy
  workflows/           Workflow states, rules, engine
  i18n/                Shared localization catalog
  utils/               Logging, metrics, security, report helpers
alembic/               Database migrations
contracts/             OpenAPI contract snapshot
ci/                    CI/test dependency helpers and baselines
docs/                  Functional, workflow, testing, and architecture docs
scripts/               Operational and worker scripts
tests/                 Unit, integration, endpoint, smoke, and E2E tests
```

---

## Prerequisites

- Python **3.10+**
- `pip` and a virtual environment tool such as `venv`
- PostgreSQL **13+** for production-like deployments
- Redis when using RQ-backed announcement dispatch or webhook/rate-limit infrastructure that depends on Redis
- Optional channel/provider credentials:
  - Meta WhatsApp Cloud API credentials
  - Telegram bot token
  - OpenAI API key only if AI features are enabled by configuration

---

## Quick start

```bash
# 1) Clone and enter the repository
git clone <repo-url>
cd society-agent

# 2) Create a virtual environment
python -m venv venv
source venv/bin/activate

# 3) Install dependencies
pip install -r requirements.txt

# 4) Create local configuration
cp .env.example .env

# 5) Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For a lightweight local/dev run, the application falls back to `sqlite:///./society_agent.db` when `DATABASE_URL` and the PostgreSQL `DB_*` variables are not provided. For staging/production and production-like validation, configure PostgreSQL explicitly.

---

## Configuration

Configuration is read from environment variables, with `.env` loaded during local development.

### Core runtime

| Variable | Default | Purpose |
|---|---:|---|
| `APP_ENV` | `local` | Environment label. Non-local environments require an explicit database URL or DB credentials. |
| `TIMEZONE` | `Asia/Kolkata` | Application timezone for society workflows. |
| `CURRENCY_SYMBOL` | `₹` | Display currency symbol. |
| `CURRENCY_CODE` | `INR` | Currency code used in finance flows. |
| `DEFAULT_SOCIETY_NAME` | unset | Optional default society name. |
| `ADMIN_PHONE_WHITELIST` | empty | Comma-separated admin phone allow-list. |
| `WHATSAPP_ENABLED` | `true` | Mount WhatsApp webhook routes when enabled. |
| `TELEGRAM_ENABLED` | `true` | Mount Telegram webhook routes when enabled. |
| `SCHEDULER_ENABLED` | `true` | Enables scheduler behavior in worker processes. |
| `CORS_ALLOWED_ORIGINS` | empty | Comma-separated allowed origins for CORS. |
| `PUBLIC_ENDPOINT_MAX_BODY_BYTES` | `131072` | Public request body size guard. |

### Database

| Variable | Default | Purpose |
|---|---:|---|
| `DATABASE_URL` | derived/fallback | Full SQLAlchemy URL for the primary database. |
| `READ_REPLICA_DATABASE_URL` | unset | Optional read-replica URL for read-only sessions. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | unset | Used to build a PostgreSQL URL when `DATABASE_URL` is not set. |
| `DB_POOL_SIZE` | env-based | SQLAlchemy pool size. |
| `DB_MAX_OVERFLOW` | env-based | SQLAlchemy max overflow connections. |
| `DB_POOL_TIMEOUT` | env-based | Pool checkout timeout in seconds. |
| `DB_POOL_RECYCLE` | env-based | Pool recycle seconds. |
| `DB_STATEMENT_TIMEOUT_MS` | env-based | PostgreSQL statement timeout. |

### Reports API authentication

| Variable | Default | Purpose |
|---|---:|---|
| `REPORTS_API_AUTH_SECRET` | unset | HMAC secret required for protected report APIs. |
| `REPORTS_API_AUTH_AUDIENCE` | unset | Optional audience claim validation. |
| `REPORTS_API_AUTH_MAX_TTL_SECONDS` | `3600` | Maximum bearer token TTL. |
| `REPORTS_API_AUTH_MAX_IAT_FUTURE_SKEW_SECONDS` | `300` | Allowed issued-at clock skew. |

### WhatsApp

| Variable | Default | Purpose |
|---|---:|---|
| `WHATSAPP_VERIFY_TOKEN` | unset | Meta webhook verification token. |
| `WHATSAPP_APP_SECRET` | unset | Meta app secret for signature verification. |
| `WHATSAPP_ACCESS_TOKEN` | unset | Cloud API access token. |
| `WHATSAPP_PHONE_NUMBER_ID` | unset | Sender phone number ID. |
| `WHATSAPP_API_VERSION` | `v22.0` | Graph API version. |
| `WHATSAPP_GRAPH_BASE_URL` | `https://graph.facebook.com` | Graph API base URL. |
| `WHATSAPP_READINESS_MODE` | `sanity` | `sanity` or `connectivity` readiness checks. |
| `WHATSAPP_CONNECTIVITY_TIMEOUT_SECONDS` | `3` | Connectivity readiness timeout. |
| `WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS` | `60` | Webhook IP rate-limit window. |
| `WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS` | `120` | Max webhook requests per window. |
| `WHATSAPP_WEBHOOK_MAX_BODY_BYTES` | `65536` | WhatsApp webhook body size limit. |
| `WHATSAPP_SENDER_SPAM_WINDOW_SECONDS` | `60` | Sender spam-rate window. |
| `WHATSAPP_SENDER_SPAM_MAX_MESSAGES` | `30` | Max messages per sender per window. |

### Telegram

| Variable | Default | Purpose |
|---|---:|---|
| `TELEGRAM_BOT_TOKEN` | unset | Telegram bot token. |
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Telegram API base URL. |
| `TELEGRAM_WEBHOOK_SECRET` | unset | Webhook secret token. |
| `TELEGRAM_WEBHOOK_MAX_BODY_BYTES` | `65536` | Telegram webhook body size limit. |

### Audit, announcements, and workers

| Variable | Default | Purpose |
|---|---:|---|
| `AUDIT_RETENTION_DAYS_BY_EVENT` | JSON defaults | Per-event audit retention configuration. |
| `AUDIT_PII_CAPTURE_MODE` | `redacted` | `none`, `redacted`, or `encrypted_raw`. |
| `AUDIT_ENCRYPTION_KEY` | unset | Optional audit encryption key. |
| `AUDIT_KMS_KEY_ID` | unset | Optional external KMS key ID. |
| `AUDIT_READ_ROLES` | `chairman,governance,admin` | Roles allowed to read audit exports/events. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL for queues/rate-limit infrastructure. |
| `ANNOUNCEMENT_DISPATCH_BACKEND` | `local` | `local` or `rq`. |
| `ANNOUNCEMENT_QUEUE_DEFAULT` | `announcement-default` | Default announcement queue name. |
| `ANNOUNCEMENT_QUEUE_WHATSAPP` | `announcement-whatsapp` | WhatsApp announcement queue name. |
| `ANNOUNCEMENT_JOB_TIMEOUT_SECONDS` | `120` | Announcement job timeout. |
| `ANNOUNCEMENT_RETRY_MAX` | `3` | Max delivery retries. |
| `ANNOUNCEMENT_RETRY_BASE_SECONDS` | `2` | Retry backoff base seconds. |
| `ANNOUNCEMENT_WORKER_CONCURRENCY_WHATSAPP` | `2` | WhatsApp worker concurrency. |
| `ANNOUNCEMENT_WORKER_CONCURRENCY_DEFAULT` | `1` | Default worker concurrency. |

### AI settings

| Variable | Default | Purpose |
|---|---:|---|
| `AI_ENABLED` | `false` in `.env.example` | Feature flag for AI behavior where implemented. |
| `AI_PROVIDER` | `openai` in `.env.example` | AI provider name. |
| `OPENAI_API_KEY` | unset | Provider API key. |

---

## Database & migrations

### PostgreSQL setup

```sql
CREATE USER society_user WITH PASSWORD 'society_pass';
CREATE DATABASE society_db OWNER society_user;
GRANT ALL PRIVILEGES ON DATABASE society_db TO society_user;
```

Then configure either:

```dotenv
DATABASE_URL=postgresql+psycopg2://society_user:society_pass@localhost:5432/society_db
```

or the component variables:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=society_db
DB_USER=society_user
DB_PASSWORD=society_pass
```

### Apply migrations

The FastAPI startup path enforces Alembic schema readiness. You can also run migrations explicitly:

```bash
alembic upgrade head
```

### Bootstrap seed

Use bootstrap seeding to initialize baseline society data, chairman identity, flats, and periodic task defaults:

```bash
python scripts/bootstrap_seed.py
```

The script uses a PostgreSQL advisory transaction lock and a `bootstrap_seed_guard` row for one-time behavior. If the guard already exists, it exits successfully without changing data. Optional seed data is read from `bootstrap.seed.json` and validated strictly.

---

## Running services

### Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run the scheduler worker

```bash
python scripts/run_scheduler.py
```

### Run announcement delivery worker

```bash
python scripts/run_announcement_worker.py
```

### Run API and scheduler on one host

```bash
scripts/run_single_server.sh
```

---

## API surface

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Basic service health. |
| `GET` | `/health/readiness/whatsapp` | WhatsApp configuration/connectivity readiness. |

### Channel webhooks

| Method | Path | Description |
|---|---|---|
| `GET` | `/whatsapp` | Meta WhatsApp webhook verification. |
| `POST` | `/whatsapp` | WhatsApp inbound webhook processing. |
| `POST` | `/telegram` | Telegram inbound webhook processing. |

### Reports APIs

Protected report APIs require a backend-signed bearer token when `REPORTS_API_AUTH_SECRET` is configured.

| Category | Paths |
|---|---|
| Financial | `/reports/financial/event-summary`, `/event-summary/export`, `/flat-payments`, `/flat-payments/export`, `/block-payments`, `/block-payments/export`, `/sponsor-contributions/export`, `/contribution-refunds/export`, `/balance-continuity/export`, `/member-refunds/export`, `/ledger/export` |
| Operations | `/reports/operations/food-pass`, `/food-pass/export`, `/pending-payments`, `/pending-payments/export`, `/expense-summary`, `/expense-summary/export`, `/participation` |
| Administrative | `/reports/admin/members/export`, `/onboarding/export`, `/announcements/export` |
| Governance | `/reports/governance/audit/export`, `/audit/events` |
| Public | `/reports/public/event-summary/pdf` |

The generated schema is versioned through `app/api/contracts.py` and snapshotted in `contracts/openapi.v1.json`.

---

## Messaging commands

The bot detects intents from localized keywords in English, Hindi, and Gujarati. Exact availability depends on the user's role, society membership, and current event state.

### Common/member commands

| Command examples | Purpose |
|---|---|
| `menu`, `help`, `more` | Show menu/help and paginate interactive options. |
| `join`, `join status` | Start or inspect onboarding. |
| `pay 500` | Record/request an event payment depending on context. |
| `refund 100 reason...` | Request or record refund behavior depending on role/context. |
| `add pass 2` | Book event passes. |
| `my pass`, `my tokens` | View personal pass/token state. |
| `my payment requests`, `my refund requests`, `my payments`, `my balance`, `my status` | View personal finance/status information. |
| `summary`, `block report`, `participation report`, `pending payments` | View available summaries/reports. |

### Committee/admin commands

| Command examples | Purpose |
|---|---|
| `add event ...`, `activate event`, `lock passes`, `start event`, `close event` | Manage event lifecycle. |
| `add sponsor 5000`, `refund sponsor ...`, `expense ...` | Manage sponsor contributions, sponsor refunds, and expenses. |
| `approve payment ...`, `approve refund ...`, `payment requests`, `refund requests` | Review and approve finance requests. |
| `pending users`, `approve user ...` | Review and approve onboarding. |
| `committee members`, `add committee member`, `remove committee member`, `change committee role` | Manage committee roster and roles. |
| `report options`, `event <n>`, `export <n>` | Use WhatsApp report export flow. |
| `announce event ...`, `announce society ...` | Queue event/society announcements. |
| `generate food tokens`, `open food counter`, `verify food token ...`, `scan food qr ...`, `serve flat ...` | Run food-token and counter operations. |
| `token status ...`, `flat passes ...`, `food dashboard` | Monitor event-day food operations. |
| `remind ...` | Trigger payment reminders. |

### Telegram-specific identity commands

| Command examples | Purpose |
|---|---|
| `link member` | Start member identity linking. |
| `verify phone` | Verify phone challenge. |

See `docs/command_access_matrix.md` and `docs/functional_workflows.md` for deeper role/state behavior.

---

## Reports

Reports are available both through HTTP endpoints and WhatsApp export flows. Current report families include:

- **Financial**: event summaries, flat/block payments, sponsor contributions, contribution refunds, balance continuity, member refunds, ledger exports.
- **Operations**: food-pass operations, pending payments, expense summaries, participation.
- **Administrative**: member exports, onboarding exports, announcement exports.
- **Governance**: audit exports and audit event listings.
- **Public**: public event-summary PDF.

---

## Operational scripts

| Script | Purpose |
|---|---|
| `scripts/bootstrap_seed.py` | Seed baseline society/chairman/flats/periodic tasks once. |
| `scripts/seed_flats.py` | Seed flats. |
| `scripts/seed_periodic_tasks.py` | Seed scheduler periodic tasks. |
| `scripts/run_scheduler.py` | Run the scheduler worker. |
| `scripts/run_announcement_worker.py` | Run announcement delivery worker. |
| `scripts/run_single_server.sh` | Start API and scheduler together on one host. |
| `scripts/map_user_to_flat.py` | Map users to flats. |
| `scripts/reset_event.py` | Reset event data for operational recovery/dev workflows. |
| `scripts/export_data.py` | Export data. |
| `scripts/backup_db.py` | Backup database. |
| `scripts/prune_audit_data.py` | Prune audit records according to retention settings. |

---

## Testing

The repository uses `pytest` with coverage enabled by `pytest.ini`.

### Full suite

```bash
pytest
```

### Useful focused commands

```bash
# Fast unit-style tests
pytest -m "not integration and not endpoint and not smoke"

# Integration and endpoint tests
pytest -m "integration or endpoint"

# Critical smoke workflows
pytest -m smoke

# WhatsApp role × event-state × language matrix
pytest tests/e2e/test_combinatorial_matrix.py
```

### Other checks

```bash
# If ruff is installed in the environment
ruff check .

# Contract/schema focused tests
pytest tests/test_contract_schema_ci.py tests/test_api_contract_integration.py
```

See `docs/testing-strategy.md` for CI stage expectations, marker policy, and reliability standards.

---

## Documentation map

| Document | Purpose |
|---|---|
| `docs/functional_workflows.md` | End-to-end functional map, module ownership, commands, and workflow behavior. |
| `docs/workflows.md` | WhatsApp workflow notes. |
| `docs/command_access_matrix.md` | Command access expectations by role/state. |
| `docs/announcements.md` | Announcement architecture and delivery policy. |
| `docs/digital_food_pass_workflow.md` | Food pass/token operational workflow. |
| `docs/society_id_policy.md` | `society_id` denormalization invariants. |
| `docs/testing-strategy.md` | Test pyramid, CI stages, marker policy, reliability standards. |
| `app/modules/scheduler/README.md` | Scheduler architecture and worker behavior. |
| `docs/CODEX_INSTRUCTIONS.md` | Detailed implementation and maintenance instructions for coding agents. |

---

## Notes for maintainers

- Keep this README aligned with `docs/functional_workflows.md`, `docs/testing-strategy.md`, route files under `app/api/*`, and command keywords under `app/channels/whatsapp/intents.py`.
- When adding WhatsApp commands, update `tests/e2e/test_combinatorial_matrix.py` so role, event-state, and language permutations remain covered.
- When adding report endpoints, update `contracts/openapi.v1.json` and relevant docs/tests.
