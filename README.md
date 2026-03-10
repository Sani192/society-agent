# Society Event Management Agent

## 1. Overview
Society Event Management Agent is a FastAPI-based backend for managing society operations such as events, payments, sponsorships, expenses, refunds, and report exports.

### Architecture (channel layer vs domain modules)
- **Channel layer (`app/channels/*`, `app/whatsapp/*`)**
  - Handles transport-specific concerns (WhatsApp/Telegram request parsing, channel adapters, response formatting, webhook protocol handling).
  - Should stay thin and delegate business behavior to domain services.
- **Domain modules (`app/modules/*`)**
  - Implement core business logic (contributions, reports, reminders, refunds, participation, etc.).
  - Are channel-agnostic and reusable across interfaces.

This separation keeps webhook logic isolated from the core domain and makes behavior easier to test and evolve.

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

### Example `.env`
```bash
APP_ENV=local
DB_HOST=localhost
DB_PORT=5432
DB_NAME=society_db
DB_USER=society_user
DB_PASSWORD=society_pass
AI_ENABLED=false
AI_PROVIDER=openai
OPENAI_API_KEY=your_key_here
WHATSAPP_MODE=SIMULATOR
TIMEZONE=Asia/Kolkata
CURRENCY_SYMBOL=₹
DEFAULT_SOCIETY_NAME=My Society
ADMIN_PHONE_WHITELIST=+911234567890,+919876543210
TELEGRAM_BOT_TOKEN=
TELEGRAM_API_BASE_URL=https://api.telegram.org
TELEGRAM_WEBHOOK_SECRET=
```

## 4. DB setup/migrations
### Initial setup
1. Create DB user and database:
   ```sql
   CREATE USER society_user WITH PASSWORD 'society_pass';
   CREATE DATABASE society_db OWNER society_user;
   GRANT ALL PRIVILEGES ON DATABASE society_db TO society_user;
   ```
2. Ensure `.env` points to those credentials.
3. Start the app once. Tables are auto-created at startup via SQLAlchemy metadata.

### Migrations for existing databases
- SQL migration files are in `docs/migrations/`.
- Apply them in chronological order (oldest to newest), for example:
  ```bash
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260223_pending_users_flat_id_migration.sql
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260223_drop_committee_member_channel_identity_phone_number.sql
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260224_backfill_committee_channel_identities.sql
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260224_flats_society_flat_number_unique.sql
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260224_requester_fk_migration.sql
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260224_society_id_consistency_guards.sql
  ```

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
5. Open:
   - API base: `http://localhost:8000`
   - Swagger UI: `http://localhost:8000/docs`

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

For full request/response schemas, use Swagger UI (`/docs`) or the OpenAPI contract file at `contracts/openapi.v1.json`.

### Single-server deployment (API + scheduler together)
If you run only one server/VM, start both processes with:
```bash
./scripts/run_single_server.sh
```
This starts the scheduler worker first, then the API server. On shutdown, it also stops the scheduler process.

## 7. Testing/development commands
Run from repository root:

- Lint:
  ```bash
  ruff check .
  ```
- Type-check regression guard:
  ```bash
  python scripts/ci/mypy_regression_guard.py
  ```
- Fast unit tests:
  ```bash
  pytest -m "not integration and not endpoint and not smoke"
  ```
- Integration + endpoint tests:
  ```bash
  pytest -m "integration or endpoint"
  ```
- Smoke tests:
  ```bash
  pytest -m smoke
  ```
- Marker policy check:
  ```bash
  python scripts/ci/check_test_markers.py
  ```
- Expenses
- Carry-forward balances
- Transparent reports

The system is designed with **full transparency** and **audit safety**.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate
- Festival events
- Food passes
- Payments & refunds
- Sponsors & donations
- Expenses
- Carry-forward balances
- Transparent reports

The system is designed with **full transparency** and **audit safety**.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate
This system helps the society managing committee manage:

- Festival events
- Food passes
- Payments & refunds
- Sponsors & donations
- Expenses
- Carry-forward balances
- Transparent reports

The system is designed with **full transparency** and **audit safety**.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate

The system is designed with **full transparency** and **audit safety**.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate
- Festival events
- Food passes
- Payments & refunds
- Sponsors & donations
- Expenses
- Carry-forward balances
- Transparent reports

The system is designed with **full transparency** and **audit safety**.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate
This system helps the society managing committee manage:

- Festival events
- Food passes
- Payments & refunds
- Sponsors & donations
- Expenses
- Carry-forward balances
- Transparent reports

The system is designed with **full transparency** and **audit safety**.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate
---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
This system helps the society managing committee manage:- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate