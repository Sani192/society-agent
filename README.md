# 🏘️ Society Event Management Agent

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

## ✅ Prerequisites

- **Python 3.10+** (and `pip`/`venv`)
- **PostgreSQL 13+** (local or remote instance)
- Optional: **OpenAI API key** if you want AI features enabled

---

## ⚙️ Environment Variables

Create a `.env` file at the repo root (the app loads it automatically) and set:

### Database (required)
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

### App/runtime
- `APP_ENV` (defaults to `local`)
- `TIMEZONE` (defaults to `Asia/Kolkata`)
- `CURRENCY_SYMBOL` (defaults to `₹`)
- `DEFAULT_SOCIETY_NAME` (used to seed default society details)
- `ADMIN_PHONE_WHITELIST` (comma-separated phone numbers)

### AI (optional)
- `AI_ENABLED` (set `true` or `false`)
- `AI_PROVIDER` (e.g. `openai`)
- `OPENAI_API_KEY`

### WhatsApp (optional)
- `WHATSAPP_MODE` (e.g. `SIMULATOR`)

Example `.env`:

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
```

---

## 🗄️ Database Setup

1. Start PostgreSQL.
2. Create a database + user:

```bash
psql -U postgres

CREATE USER society_user WITH PASSWORD 'society_pass';
CREATE DATABASE society_db OWNER society_user;
GRANT ALL PRIVILEGES ON DATABASE society_db TO society_user;
```

3. Ensure your `.env` matches these values.
4. The app auto-creates tables on startup.

---

## 🚀 How to Run (Local)

### 1️⃣ Activate virtual environment

```bash
source venv/bin/activate
```

### 2️⃣ Install dependencies

If you have a `requirements.txt` or similar lockfile, install from it. Otherwise, install the core packages:

```bash
python -m pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv
```

### 3️⃣ Run the FastAPI app

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

---

## 📡 Basic API Endpoints

- **Health check:** `GET /health`
- **WhatsApp webhook:** `POST /whatsapp`
- **Reports (examples):**
  - `GET /reports/financial/event-summary`
  - `GET /reports/financial/flat-payments`
  - `GET /reports/admin/members/export`
  - `GET /reports/admin/onboarding/export`
  - `GET /reports/governance/audit/export`
  - `GET /reports/public/event-summary/pdf`

Swagger UI is available at: `http://localhost:8000/docs`
This system helps the society managing committee manage:- Festival events- Food passes- Payments & refunds- Sponsors & donations- Expenses- Carry-forward balances- Transparent reportsThe system is designed with **full transparency** and **audit safety**.---## 🚀 How to Run (Local)### 1️⃣ Activate virtual environment```bashsource venv/bin/activate