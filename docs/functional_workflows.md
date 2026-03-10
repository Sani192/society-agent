# Functional Workflows & Module Guide

This document is the **end-to-end functional map** of the Society Event Management Agent: what it does, which module owns what, which commands are available, who can use them, and when each command should be used.

---

## 1) What this application does

Society Event Management Agent is a FastAPI backend for society operations across:

- Event lifecycle management
- Member onboarding/join approvals
- Pass booking and food token serving
- Payments, refunds, sponsor contributions, expenses
- Announcements
- Reports (financial, governance, administrative, public)
- Channel interfaces (WhatsApp and Telegram)

---

## 2) Architecture: who does what

## 2.1 Entry/API layer

- `app/main.py`
  - Boots FastAPI app
  - Creates DB schema on startup
  - API process starts only HTTP routes (no background schedulers)
  - Mounts webhook/report/health APIs
- `scripts/run_scheduler.py`
  - Dedicated scheduler worker process
  - Acquires advisory-lock leadership and starts reminder + announcement schedulers only for leader role
- `scripts/run_single_server.sh`
  - Single-host launcher that starts both scheduler worker and API process together
- `app/api/*`
  - `health.py`: health endpoint
  - `whatsapp/webhook.py`: WhatsApp webhook HTTP entrypoint
  - `telegram.py`: Telegram webhook HTTP entrypoint
  - `reports/*`: report export endpoints
  - `contracts.py`: API schema version contract

## 2.2 Channel/interaction layer

- `app/channels/whatsapp/*`
  - WhatsApp adapter/client, UI routing, approval flows, report flow, session flows
- `app/channels/telegram/*`
  - Telegram adapter/client
- `app/channels/core/*`
  - Shared channel abstractions/types/auditing hooks
- `app/commands/*`
  - `parser.py`: parse amounts, pass counts, reasons, event payloads
  - `router.py`: map incoming message text to intent
  - `handlers/*`: channel-agnostic intent handlers (public/committee/onboarding)
- `app/handlers/shared/*`
  - Actual shared business orchestration used by command handlers

## 2.3 Domain modules (business logic)

- `app/modules/events/*`: event lifecycle + food pass/token/serving logic
- `app/modules/payments/*`: payment capture + payment/refund request workflows
- `app/modules/contributions/*`: sponsor contributions and sponsor refunds
- `app/modules/expenses/*`: expense tracking
- `app/modules/ledger/*`: ledger/balance continuity data
- `app/modules/onboarding/*`: join code, pending users, approval flows
- `app/modules/committee/*`: committee member administration
- `app/modules/announcements/*`: announcement composition + delivery worker
- `app/modules/reminders/*`: reminder scheduling and dispatch
- `app/modules/reports/*`: report data + exporters/PDF generators
- `app/modules/users/*`: identity resolution, member-flat mappings, user queries

## 2.4 Data, policy, and utilities

- `app/db/*`: SQLAlchemy models/session/base
- `app/permissions/*`: role/actions and command-state policy guards
- `app/workflows/*`: event state machine rules and workflow engine
- `app/utils/*`: logging, response parser, time, guards, audit helpers

---

## 3) Core business workflows (functional)

## 3.1 Onboarding workflow

**Goal:** bring a resident into the system and map them to a flat/society identity.

Typical flow:
1. User sends `join`.
2. System starts join flow and captures details.
3. User can check progress using `join status`.
4. Committee (chairman) reviews via `pending users`.
5. Chairman approves via `approve user`.
6. User becomes active member mapping and can use member commands.

Owned by:
- `app/modules/onboarding/*`
- `app/handlers/shared/onboarding.py`
- `app/channels/whatsapp/session_flows.py`, `app/whatsapp/join_session.py`

## 3.2 Event lifecycle workflow

**Goal:** move event through state machine with controlled transitions.

State progression:

`DRAFT -> ACTIVE -> LOCKED -> EVENT_DAY -> CLOSED`

Commands/transitions:
- `add event` (create)
- `activate event`
- `lock passes`
- `start event`
- `close event`

Owned by:
- `app/modules/events/service.py`
- `app/workflows/states.py`, `app/workflows/rules.py`, `app/workflows/engine.py`
- `app/handlers/shared/committee.py`

## 3.3 Member pass + payment workflow

**Goal:** collect participation intent and settle expected amount.

Flow:
1. Member sends `add pass veg X jain Y kids Z`.
2. System computes expected amount using event adult/child charges.
3. Member sends `pay <amount>`.
4. Depending on permissions/context:
   - request-based flow (`PaymentRequestService`) for approval
   - direct recording (`PaymentService`) by authorized committee actor
5. Member can inspect with `my pass`, `my payments`, `my balance`, `my status`.

Owned by:
- `app/modules/events/food_pass_service.py`
- `app/modules/payments/payment_service.py`, `payment_request_service.py`
- `app/modules/users/user_query_service.py`

## 3.4 Refund workflow (member + sponsor)

**Member refund:**
- User: `refund <amount> reason <text>`
- Creates refund request or direct process based on actor role/context.

**Sponsor refund:**
- Committee: `refund sponsor ...`
- Goes through contribution refund service with role guard.

Owned by:
- `app/modules/payments/refund_service.py`, `refund_request_service.py`
- `app/modules/contributions/contribution_refund_service.py`

## 3.5 Food token + serving workflow (event day)

**Goal:** operational food distribution with token auditability.

Flow:
1. Committee generates tokens: `generate food tokens` (LOCKED/EVENT_DAY).
2. Opens counter: `open food counter` (EVENT_DAY).
3. Serving actions:
   - `verify food token <token>`
   - `scan food qr <payload>`
   - `serve flat <flat>`
4. Monitoring:
   - `token status <token>`
   - `flat passes <flat>`
   - `food dashboard`
5. Member visibility: `my tokens`, `my pass`.

Owned by:
- `app/modules/events/food_collection_service.py`

## 3.6 Announcements workflow

Flow:
1. Committee triggers event/society announcement:
   - `announce event <message>`
   - `announce society <message>`
2. Manager builds recipient set and message payload.
3. Delivery worker pushes asynchronously with retry/reliability envelope.

Owned by:
- `app/modules/announcements/manager.py`
- `app/modules/announcements/delivery_worker.py`
- `app/modules/announcements/recipient_service.py`

## 3.7 Reporting workflow

Paths:
- **Interactive WhatsApp exports** via `report options` + `event <n>` + `export <n>` or `export::<id>`
- **HTTP report endpoints** under `/reports/*`
- **PDF exporters** in `app/modules/reports/pdf/*`

Typical committee flow:
1. Send `report options`
2. Pick event / report option
3. Export generated output (channel or endpoint response)

Owned by:
- `app/modules/reports/*`
- `app/modules/reports/common/whatsapp_report_registry.py`
- `app/modules/reports/whatsapp_export_service.py`

---

## 4) Command catalog: how to use, when to use, who can use

> Command text matching is intent-driven (`app/whatsapp/intents.py` + `app/commands/router.py`).
> Final availability also depends on event-state policy (`app/permissions/command_policy.py`) and role guard.

## 4.1 Public/member commands

| Command | Purpose | Who can use | When to use |
|---|---|---|---|
| `join` | Start onboarding | Unregistered/public users | First time setup |
| `join status` | Track onboarding status | Users in onboarding | After submit, before approval |
| `menu` / `help` | See available actions | Everyone | Any time |
| `add pass ...` | Add/update pass counts | Member / delegated committee context | Event ACTIVE/LOCKED/EVENT_DAY |
| `pay <amount>` | Submit payment request or record payment | Member / committee | Event ACTIVE/LOCKED/EVENT_DAY |
| `refund <amount> reason ...` | Request/process member refund | Member / committee | Event ACTIVE/LOCKED/EVENT_DAY |
| `my pass` | View pass + served summary | Member | Event ACTIVE/LOCKED/EVENT_DAY |
| `my tokens` | View token list/status | Member | After tokens generated |
| `my payment requests` | View own payment requests | Member | Event ACTIVE/LOCKED/EVENT_DAY |
| `my refund requests` | View own refund requests | Member | Event ACTIVE/LOCKED/EVENT_DAY |
| `my payments` | View payment summary | Member | Event ACTIVE/LOCKED/EVENT_DAY |
| `my balance` | View expected/paid/remaining | Member | Event ACTIVE/LOCKED/EVENT_DAY |
| `my status` | View event status snapshot | Member | Event ACTIVE/LOCKED/EVENT_DAY |
| `summary` | Public event summary | Member/committee | Event ACTIVE/LOCKED/EVENT_DAY |
| `block report` | Block-wise contribution quick report | Member/committee | Event ACTIVE/LOCKED/EVENT_DAY |

## 4.2 Committee commands

| Command | Purpose | Who can use | Event state |
|---|---|---|---|
| `add event` | Create event (direct format or wizard flow) | Committee (role-guarded) | DRAFT |
| `activate event` | Move DRAFT -> ACTIVE | Committee | DRAFT |
| `lock passes` | Move ACTIVE -> LOCKED | Committee | ACTIVE |
| `start event` | Move LOCKED -> EVENT_DAY | Committee | LOCKED |
| `close event` | Move EVENT_DAY -> CLOSED | Committee (role-guarded) | EVENT_DAY |
| `expense ...` | Add expense | Committee (role-guarded) | ACTIVE/LOCKED/EVENT_DAY |
| `add sponsor ...` | Add sponsor contribution | Committee (role-guarded) | ACTIVE/LOCKED/EVENT_DAY |
| `refund sponsor ...` | Refund sponsor contribution | Committee (role-guarded) | ACTIVE/LOCKED/EVENT_DAY |
| `remind ...` | Send pending-payment reminder | Committee (role-guarded) | ACTIVE/LOCKED/EVENT_DAY |
| `pending payments` | List payment pendings | Committee | ACTIVE/LOCKED/EVENT_DAY |
| `payment requests` | View/triage payment requests | Committee | ACTIVE/LOCKED/EVENT_DAY |
| `refund requests` | View/triage refund requests | Committee | ACTIVE/LOCKED/EVENT_DAY |
| `approve payment ...` | Approve payment request | Committee | ACTIVE/LOCKED/EVENT_DAY |
| `approve refund ...` | Approve refund request | Committee | ACTIVE/LOCKED/EVENT_DAY |
| `report options` | Open export menu | Committee | DRAFT/ACTIVE/LOCKED/EVENT_DAY/CLOSED |
| `participation report` | Participation-focused report | Committee | DRAFT/ACTIVE/LOCKED/EVENT_DAY/CLOSED |
| `announce event ...` | Event-targeted announcement | Committee | Usually active ops windows |
| `announce society ...` | Society-wide announcement | Committee | Any operations window |

## 4.3 Committee onboarding/admin commands

| Command | Purpose | Who can use | Notes |
|---|---|---|---|
| `pending users` | List users awaiting approval | Chairman | Chairman-only policy |
| `approve user ...` | Approve pending onboarding user | Chairman | Chairman-only policy |
| `committee members` | List committee roster | Committee admins | Management flow |
| `add committee member <name|phone|role>` | Add committee member identity | Committee admins | Role must be valid |
| `remove committee member <member_id>` | Remove committee member | Committee admins | Guarded operation |
| `change committee role <member_id> <role>` | Change committee role | Committee admins | Guarded operation |

## 4.4 Event-day food operations commands

| Command | Purpose | Who can use | Event state |
|---|---|---|---|
| `generate food tokens` | Generate token inventory | Committee | LOCKED/EVENT_DAY |
| `open food counter` | Mark serving as open | Committee | EVENT_DAY |
| `verify food token ...` | Verify token and serve | Committee | EVENT_DAY |
| `scan food qr ...` | QR-based verification & serving | Committee | EVENT_DAY |
| `serve flat ...` | Fallback serve by flat | Committee | EVENT_DAY |
| `flat passes ...` | Flat-level pass/serve status | Committee | EVENT_DAY |
| `token status ...` | Token-level status check | Committee | EVENT_DAY |
| `food dashboard` | Food serving operational metrics | Committee | EVENT_DAY |

## 4.5 Telegram-only identity commands

| Command | Purpose | Who can use | Channel |
|---|---|---|---|
| `link member` | Link channel identity to member | Member + committee support | Telegram only |
| `verify phone` | Verify member phone mapping | Member | Telegram only |

---

## 5) Role model (who can do what)

Primary committee roles:
- `chairman`
- `secretary`
- `treasurer`
- `committee_member`

Policy behavior:
- Chairman has full access (`ALL`) in action policy.
- Secretary and Treasurer have scoped operational actions.
- Committee member has limited operational/report visibility.
- Some commands additionally enforce specific role conditions (example: pending user approvals are chairman-only).

See:
- `app/permissions/roles.py`
- `app/permissions/guard.py`
- `app/permissions/command_policy.py`

---

## 6) State-driven command gating (when to use which command)

The platform prevents invalid operations based on event state.

- Use **DRAFT** for setup (`add event`, `activate event`)
- Use **ACTIVE** for member collection (`add pass`, `pay`, sponsor/expense, reminders)
- Use **LOCKED** when participation is frozen but finance/admin still active
- Use **EVENT_DAY** for serving/token operations and last-mile finance/admin
- Use **CLOSED** for post-event reporting/readonly operations

If a command is disallowed in current state, users get a warning and command is blocked.

---

## 7) Programmatic/operational commands (repo usage)

## 7.1 Run app

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 7.2 Common test & quality commands

```bash
ruff check .
python scripts/ci/mypy_regression_guard.py
pytest -m "not integration and not endpoint and not smoke"
pytest -m "integration or endpoint"
pytest -m smoke
python scripts/ci/check_test_markers.py
```

## 7.3 Utility scripts (when to use)

- `scripts/seed_flats.py` — initialize flat master data
- `scripts/seed_reminder_config.py` — seed reminder settings
- `scripts/map_user_to_flat.py` — manual identity/flat mapping
- `scripts/reset_event.py` — reset an event for controlled test rerun
- `scripts/backfill_member_identities.py` — identity migration/backfill
- `scripts/backfill_committee_channel_identities.py` — committee identity normalization
- `scripts/export_data.py` — data export utility
- `scripts/backup_db.py` — database backup
- `scripts/ci/reset_test_state.py` — reset CI test DB state
- `scripts/ci/reliability_dashboard.py` — reliability signal aggregation

---

## 8) End-user quick usage scenarios

## Scenario A: New resident joins and participates
1. `join`
2. Wait for approval (`join status`)
3. `add pass veg 2 jain 1`
4. `pay 900`
5. Track with `my balance`, `my pass`

## Scenario B: Committee runs full event
1. `add event` (wizard or inline format)
2. `activate event`
3. Monitor `pending payments`, send `remind`
4. `lock passes`
5. `start event`
6. `generate food tokens` and `open food counter`
7. Use `verify food token` / `scan food qr` during serving
8. `close event`
9. `report options` and export reports

## Scenario C: Finance exception handling
1. Resident requests `refund 200 reason guest absent`
2. Treasurer reviews in `refund requests`
3. Treasurer runs `approve refund <request>`

---

## 9) Important companion docs

- `docs/workflows.md` — WhatsApp workflow notes
- `docs/command_access_matrix.md` — command visibility/execution matrix
- `docs/digital_food_pass_workflow.md` — food pass/token details
- `docs/announcements.md` — announcement design and delivery
- `docs/society_id_policy.md` — society identity integrity model
- `docs/testing-strategy.md` — test strategy and marker conventions
