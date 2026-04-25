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
3. (Optional for local bootstrap) Apply the baseline schema directly:
   ```bash
   psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f docs/migrations/20260319_baseline_schema.sql
   ```
4. Start the app.

### Bootstrap Seeding
Use bootstrap seeding to initialize baseline records (society, chairman, chairman channel identity, flats, reminder config) in a single guarded transaction.

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
     - `reminder_defaults`: `enabled` (optional boolean), `frequency` (`daily|weekly`), `run_hour` (`0..23`), `run_minute` (`0..59`)
   - Example:
   ```json
   {
     "society": {
       "name": "Sunrise Residency",
       "city": "Ahmedabad",
       "state": "Gujarat",
       "timezone": "Asia/Kolkata"
     },
     "onboarding": {
       "join_code": "JOIN123",
       "approval_required": true
     },
     "chairman": {
       "name": "Amit Shah",
       "phone": "+919999000001",
       "channel_identity": {
         "channel_type": "whatsapp",
         "external_user_id": "+919999000001",
         "username": null
       }
     },
     "flats": [
       { "flat_number": "A-101", "block": "A", "owner_name": "Rita Patel" },
       { "flat_number": "A-102", "block": "A", "owner_name": "Mihir Patel" }
     ],
     "reminder_defaults": {
       "enabled": true,
       "frequency": "daily",
       "run_hour": 10,
       "run_minute": 0
     }
   }
   ```

5. Supported environment overrides:
   - `BOOTSTRAP_SEED_FILE`: absolute/relative path to config JSON. If set and missing/invalid, script fails.
   - `BOOTSTRAP_FLATS_FILE`: CSV-like file input for flats (`flat_number,block,owner_name` per line; `#` comments allowed).
   - `BOOTSTRAP_FLATS_LIST`: inline flats list (`flat,block,owner;flat,block,owner`), used when file is not set.
   - `BOOTSTRAP_CHAIRMAN_PHONE`, `BOOTSTRAP_CHAIRMAN_NAME`
   - `BOOTSTRAP_CHAIRMAN_EXTERNAL_USER_ID`, `BOOTSTRAP_CHAIRMAN_USERNAME`
   - `BOOTSTRAP_JOIN_CODE`, `BOOTSTRAP_APPROVAL_REQUIRED`
   - Notes:
     - Values from `bootstrap.seed.json` take precedence for fields they define.
     - Flats precedence: `bootstrap.seed.json` `flats` → `BOOTSTRAP_FLATS_FILE` → `BOOTSTRAP_FLATS_LIST` → script defaults.

6. Expected log stages and troubleshooting:
   - Per stage log envelope:
     - `START <stage>`
     - `SUCCESS <stage>`
     - `FAIL <stage>` (stderr)
   - Typical stages: `initialization`, `check guard`, `seed society`, `seed first chairman`, `seed chairman channel identity`, `seed flats`, `seed reminder config`, `verify seeded data`, `mark bootstrap as completed`.
   - On fatal error, script prints: `bootstrap failed at stage '<stage>': <error>`.
   - Troubleshooting:
     - Malformed config:
       - JSON parse/shape errors raise `Invalid bootstrap config: ...`.
       - Fix JSON syntax and required fields/types/ranges listed above.
     - Missing table:
       - Errors like relation/table not found (for example `bootstrap_seed_guard`, `societies`, `flats`, etc.) indicate schema is not applied.
       - Apply baseline schema/migrations first, then re-run.
     - Uniqueness errors:
       - Duplicate keys (for example chairman channel identity uniqueness) abort the transaction and roll everything back.
       - Resolve conflicting existing data (or reset DB), then re-run bootstrap once.

### Environment behavior on startup
- `APP_ENV=local` or `APP_ENV=dev`: application startup can auto-create missing tables for local development convenience.
- `APP_ENV=staging` or `APP_ENV=production`: startup validates schema readiness before serving traffic.
- Optional controlled automation: set `STARTUP_MIGRATIONS_ENABLED=true` to run SQL migrations from `docs/migrations/*.sql` during startup.
- `schema_migrations` is used to track applied migration filenames so each SQL migration runs once per database.
- If migrations are still pending after pipeline execution, startup fails fast when required tables **or model columns** are missing so the rollout can be stopped safely.

### Schema reference
- The canonical baseline schema lives at `docs/migrations/20260319_baseline_schema.sql`.
- Historical SQL patches in `docs/migrations/` are applied incrementally by the startup migration pipeline in lexical filename order.
- Any schema-changing code update should include a new SQL migration file under `docs/migrations/` to keep runtime schema and model metadata in sync.
- CI/test guard `tests/test_migration_schema_guard.py` verifies the migration SQL bundle declares all current ORM model tables and columns.

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
- Localization literal guard:
  ```bash
  python scripts/ci/check_localization_literals.py
  ```

This system helps the society managing committee manage:- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate
This system helps the society managing committee manage:- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate