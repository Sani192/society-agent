# Codex Master Instructions – Society Event Management Agent

You are working on the **Society Event Management Agent**, a FastAPI backend for society operations across WhatsApp, Telegram, HTTP report APIs, scheduler workers, and domain services.

This file must be kept in sync with the codebase. Before implementing future changes, use it as the operating map for architecture, permissions, workflows, tests, and documentation updates.

---

## Primary objective (strict)

Use this repository to **fix bugs, close implementation/documentation discrepancies, and eliminate reliance on manual testing** for core behavior. Every non-trivial change should leave the codebase more automated, more testable, and better documented than before.

When Codex is asked to scan, refactor, debug, or add features, it must:

1. Compare the request against the current codebase rather than assuming this file is already complete.
2. Identify mismatches between documentation, tests, permissions, workflows, command catalogs, configuration, and implementation.
3. Fix the underlying code or documentation gap.
4. Add or update automated tests so the behavior can be validated without manual WhatsApp/Telegram/API testing.
5. Run the full available automated suite and iterate until it passes, unless an environment blocker prevents execution.

---

## Execution phases (mandatory)

Codex must work in phases. Do not jump directly to implementation for bug-fix, refactor, workflow, command, permission, channel, or core-module tasks.

### Phase 1: Understand and scan

- Read the relevant code paths end to end.
- Scan the current implementation for discrepancies against this file, `README.md`, module READMEs, and related docs in `docs/`.
- Identify the owning layers involved:
  - API/webhook entry point
  - channel adapter/session/UI layer
  - command parser/router
  - shared handler/orchestration layer
  - domain service module
  - permission and workflow rules
  - database model/migration
  - i18n/response templates
  - tests and docs
- Identify coupling, missing validation, untested branches, and edge cases.

### Phase 2: Plan before editing

Before writing code, define:

1. The bug, discrepancy, or missing behavior to fix.
2. The files and layers that must change.
3. The automated tests that will prove the fix.
4. Any docs/configuration/migration updates required.
5. Risks to existing APIs, webhook contracts, command text, reports, or data models.

### Phase 3: Implement in the correct layer

- Keep API/webhook code thin.
- Put business logic in domain services or shared handlers.
- Put permission and event-state behavior in centralized policy/workflow modules.
- Put user-facing language in i18n catalogs or response templates.
- Preserve existing public APIs and command compatibility unless explicitly changing them with tests/docs.

### Phase 4: Generate or update automated tests

Add or update pytest coverage for the changed behavior. You **MUST** update the Combinatorial Test Matrix (`tests/e2e/test_combinatorial_matrix.py`) for any new WhatsApp command or functionality. Add the command to the `COMMANDS` list and define its expected outcomes in `get_expected_response_type` to ensure it is automatically tested against all permutations of Role × Event State × Language.

Tests should cover, as applicable:

- valid and invalid inputs
- empty/malformed messages or payloads
- unauthorized access
- event-state blocking
- role-based access
- language-specific responses without mixed-language output
- webhook/API payload simulations
- idempotency/retry/rate-limit/audit paths for channel changes

### Phase 5: Simulate external interactions in tests

Do not rely on manual WhatsApp, Telegram, or HTTP testing for core flows. Simulate provider payloads, command text, webhook requests, report requests, and session/UI selections in automated tests.

### Phase 6: Full-suite debug loop

- Run the full available automated test suite.
- If any test fails, fix the failure.
- Re-run the full suite until all tests pass.
- If an environment limitation blocks the suite, report the blocker clearly and do not claim completion.

### Phase 7: Validate completion

Before finishing, ensure:

- no crashes on expected edge cases
- correct permissions and event-state behavior
- correct language selection and localized output
- no mixed-language responses
- docs match code
- no manual testing is required for the changed core behavior

### Phase 8: Output

Report:

1. Summary of changes.
2. Bugs/discrepancies found and fixed.
3. Automated tests/checks run.
4. Remaining risks or blockers, if any.

---

## 1. Current system context

### 1.1 Application purpose

The application manages society event and administrative operations, including:

- Society, flat, committee, and resident identity management.
- Resident onboarding and approval workflows.
- Event lifecycle management.
- Food pass booking, token generation, QR/token verification, and serving operations.
- Payments, payment requests, refunds, sponsor contributions, sponsor refunds, expenses, and ledger continuity.
- Announcements and delivery tracking.
- Financial, administrative, governance, operational, public, and personal reports with PDF/export support.
- WhatsApp and Telegram channel integrations.
- Scheduler/reminder/background worker processes.
- Channel audit, webhook envelope/idempotency, dead-letter, and operational metrics support.

### 1.2 Runtime stack

- Python 3.10+.
- FastAPI / Starlette API server.
- SQLAlchemy ORM with PostgreSQL.
- Alembic migrations.
- pytest test suite with coverage.
- Redis/RQ for announcement dispatch and webhook/rate-limit infrastructure where enabled.
- APScheduler for database-driven periodic tasks.
- ReportLab, Pillow, and OpenPyXL for report/document generation.

---

## 2. Architecture map

### 2.1 Entry points

- `app/main.py`
  - Creates the FastAPI application.
  - Runs schema readiness / Alembic migration enforcement during lifespan startup.
  - Applies CORS, request-size, security-header, and request-logging middleware.
  - Mounts health, WhatsApp, Telegram, and report routers according to configuration.
- `app/api/health.py`
  - Health/readiness endpoints.
- `app/api/whatsapp/webhook.py`
  - WhatsApp HTTP webhook verification and message ingress.
  - Handles signature/config validation, payload parsing, rate limiting, envelope/idempotency behavior, retry/dead-letter paths, audit events, and provider send failures.
- `app/api/telegram.py`
  - Telegram webhook ingress.
- `app/api/reports/*`
  - HTTP report export APIs for financial, administrative, governance, public, and operations reports.
- `app/api/auth.py`
  - Bearer-token principal authentication for report APIs.
- `app/api/contracts.py`
  - API schema/version response contracts.
- `scripts/run_scheduler.py`
  - Dedicated scheduler worker process using `SchedulerManager`.
- `scripts/run_announcement_worker.py`
  - Announcement delivery worker process.
- `scripts/run_single_server.sh`
  - Single-host helper to run API plus scheduler together.

### 2.2 Channel layer

Channel code must remain transport-specific and thin. It should parse/normalize incoming messages, route interaction/session/UI concerns, format replies, and delegate business behavior to domain modules or shared handlers.

- `app/channels/core/*`
  - Shared channel types, audit helpers, webhook runtime helpers, and `handle_inbound_message` orchestration.
  - Resolves sender identity/language/society/event context, detects intent, applies command-state policy, and delegates to onboarding/committee/public handlers.
- `app/channels/whatsapp/*`
  - WhatsApp adapter/client/constants/config validation.
  - Intent catalog, localized command parsing, response templates, report flow, session flows, event creation/committee/finance sessions, UI router, and UI handlers.
- `app/channels/whatsapp/webhook/*`
  - Decomposed webhook concerns: auth, audit, ingest, limits, processing, retry.
- `app/channels/telegram/*`
  - Telegram adapter/client/constants.
  - Telegram member-link and phone-verification flows are supported by shared core handling.

### 2.3 Command and handler layer

- `app/commands/parser.py`
  - Parses structured command details such as amounts, pass counts, reasons, event payloads, and report/export selections.
- `app/commands/router.py`
  - Detects localized intents from text.
  - Supports English, Hindi, and Gujarati keywords.
  - Avoids unsafe fuzzy/prefix matching for high-risk commands.
  - Provides localized near-match feedback for invalid commands.
- `app/handlers/shared/*`
  - Channel-agnostic business orchestration for public, committee, onboarding, and common command behavior.

### 2.4 Domain modules

Business rules belong in `app/modules/*`, not in webhook/controller code.

- `app/modules/announcements/*`
  - Announcement creation/recipient resolution/delivery/management.
- `app/modules/audit/*`
  - Audit retention/pruning.
- `app/modules/committee/*`
  - Committee member CRUD/role administration.
- `app/modules/contributions/*`
  - Sponsor contributions and sponsor refunds.
- `app/modules/events/*`
  - Event lifecycle, food pass booking, token generation, food collection/serving.
- `app/modules/expenses/*`
  - Expense capture.
- `app/modules/ledger/*`
  - Ledger and balance continuity.
- `app/modules/onboarding/*`
  - Join codes, pending user requests, admin approval/query services.
- `app/modules/payments/*`
  - Payment recording, payment requests, refunds, refund requests.
- `app/modules/reminders/*`
  - Reminder generation/scheduling behavior.
- `app/modules/reports/*`
  - Report services, common filters/resolvers/exporters, PDF generators, and WhatsApp export registry.
- `app/modules/scheduler/*`
  - Database-driven scheduler manager.
- `app/modules/security/*`
  - Access-control helpers.
- `app/modules/users/*`
  - Language resolution, user/member identity, flat mapping, channel identity linking.

### 2.5 Data, policy, utilities, and workflows

- `app/db/models.py`
  - SQLAlchemy models listed in section 5.
- `app/db/session.py`, `app/db/base.py`
  - Engine/session/base configuration.
- `app/permissions/*`
  - Role/action grants, command-state policy, report guards, and generic permission guards.
- `app/workflows/*`
  - Event state machine states/rules and workflow engine.
- `app/i18n/catalog.py`
  - Shared translation catalog.
- `app/utils/*`
  - Logging, audit/security logging, operational metrics, response formatting, validation, identity normalization, time/currency helpers, and channel response parsing.

---

## 3. Supported roles, languages, and event states

### 3.1 Roles

Committee roles currently recognized by policy:

- `chairman`
  - Has `ALL` role actions.
- `secretary`
  - Can handle event/expense/summary/pending/onboarding override/audit/sponsor operations granted in `ROLE_ACTIONS`.
- `treasurer`
  - Can handle payment/refund/summary/pending/sponsor/close-event operations granted in `ROLE_ACTIONS`.
- `committee_member`
  - Can handle summary, pending payments, and onboarding pending actions granted in `ROLE_ACTIONS`.

Non-committee residents are represented through `MemberIdentity` + `UserFlatMapping`; they are not committee actors. Unlinked/public senders can use onboarding/help/menu-style flows where available.

### 3.2 Languages

Localized command detection and response behavior supports:

- English: `en`
- Hindi: `hi`
- Gujarati: `gu`

Language resolution is handled through `app/modules/users/language_service.py`. New user-facing text should be placed in the i18n/response-template catalogs instead of hard-coding English in business logic.

### 3.3 Event states

The current event lifecycle states are:

```text
DRAFT -> ACTIVE -> LOCKED -> EVENT_DAY -> CLOSED
```

There is no current `expired` event state in code. Do not reintroduce the older `active / expired / none` model unless the code and docs are intentionally migrated together.

---

## 4. Current command/intent inventory

Intent keywords are defined in `app/channels/whatsapp/intents.py`; command-state gating is defined in `app/permissions/command_policy.py`; workflow action mappings are defined in `app/workflows/rules.py`.

### 4.1 Onboarding and identity

- `join`
- `join status`
- `approve user`
- `pending users`
- Telegram-only: `link member`
- Telegram-only: `verify phone`

### 4.2 Navigation/help

- `menu`
- `help`
- `report options`

### 4.3 Event lifecycle

- `add event`
- `activate event`
- `lock passes`
- `start event`
- `close event`

### 4.4 Participation, payments, and personal status

- `add pass`
- `pay`
- `refund`
- `my pass`
- `my tokens`
- `my payment requests`
- `my refund requests`
- `my payments`
- `my balance`
- `my status`

### 4.5 Committee finance and administration

- `expense`
- `add sponsor`
- `refund sponsor`
- `pending payments`
- `payment requests`
- `refund requests`
- `approve payment`
- `approve refund`
- `remind`
- `committee members`
- `add committee member`
- `remove committee member`
- `change committee role`
- `announce event`
- `announce society`

### 4.6 Food operations

- `generate food tokens`
- `open food counter`
- `verify food token`
- `scan food qr`
- `serve flat`
- `flat passes`
- `token status`
- `food dashboard`

### 4.7 Reports and exports

- `summary`
- `block report`
- `participation report`
- `report options`
- Numeric/export selections through active WhatsApp export sessions.

---

## 5. Current database model inventory

The current SQLAlchemy model set includes:

- Bootstrap/configuration:
  - `BootstrapSeedGuard`
  - `Society`
- Committee/channel identity:
  - `CommitteeMember`
  - `CommitteeMemberChannelIdentity`
  - `CommitteeMemberLinkCode`
  - `CommitteeMemberPhoneLinkChallenge`
- Channel audit/webhook runtime:
  - `ChannelConversation`
  - `ChannelMessageEvent`
  - `ChannelDeadLetter`
  - `InboundWebhookEnvelope`
  - `WebhookIdempotencyKey`
- Society/member mapping:
  - `Flat`
  - `MemberIdentity`
  - `UserFlatMapping`
  - `PendingUser`
- Event and food operations:
  - `Event`
  - `EventFoodPass`
  - `EventFoodToken`
  - `EventFoodCounter`
- Money movement:
  - `Payment`
  - `Refund`
  - `PaymentRequest`
  - `RefundRequest`
  - `EventContribution`
  - `ContributionRefund`
  - `EventExpense`
  - `SocietyBalance`
- Workflows/scheduler/reminders:
  - `WorkflowState`
  - `PeriodicTask`
  - `PaymentReminder`
- Audit/announcements:
  - `AuditLog`
  - `Announcement`
  - `AnnouncementDelivery`

When adding or changing models, update Alembic migrations, affected services/tests, and documentation.

---

## 6. Important environment/configuration surface

Configuration is centralized in `app/config.py`, with WhatsApp/Telegram provider-specific keys also declared in channel constants.

### 6.1 Core runtime

- `APP_ENV`
- `TIMEZONE`
- `CURRENCY_SYMBOL`
- `CURRENCY_CODE`
- `DEFAULT_SOCIETY_NAME`
- `ADMIN_PHONE_WHITELIST`
- `WHATSAPP_ENABLED`
- `TELEGRAM_ENABLED`
- `SCHEDULER_ENABLED`
- `STARTUP_MIGRATIONS_ENABLED`
- `CORS_ALLOWED_ORIGINS`
- `PUBLIC_ENDPOINT_MAX_BODY_BYTES`

### 6.2 Database

- `DATABASE_URL`
- `READ_REPLICA_DATABASE_URL`
- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_TIMEOUT`
- `DB_POOL_RECYCLE`
- `DB_STATEMENT_TIMEOUT_MS`

### 6.3 Reports API auth

- `REPORTS_API_AUTH_SECRET`
- `REPORTS_API_AUTH_AUDIENCE`
- `REPORTS_API_AUTH_MAX_TTL_SECONDS`
- `REPORTS_API_AUTH_MAX_IAT_FUTURE_SKEW_SECONDS`

### 6.4 Audit/security

- `AUDIT_RETENTION_DAYS_BY_EVENT`
- `AUDIT_PII_CAPTURE_MODE`
- `AUDIT_ENCRYPTION_KEY`
- `AUDIT_KMS_KEY_ID`
- `AUDIT_READ_ROLES`

### 6.5 Redis, announcements, and workers

- `REDIS_URL`
- `ANNOUNCEMENT_QUEUE_DEFAULT`
- `ANNOUNCEMENT_QUEUE_WHATSAPP`
- `ANNOUNCEMENT_JOB_TIMEOUT_SECONDS`
- `ANNOUNCEMENT_RETRY_MAX`
- `ANNOUNCEMENT_RETRY_BASE_SECONDS`
- `ANNOUNCEMENT_WORKER_CONCURRENCY_WHATSAPP`
- `ANNOUNCEMENT_WORKER_CONCURRENCY_DEFAULT`
- `ANNOUNCEMENT_DISPATCH_BACKEND`

### 6.6 WhatsApp runtime

- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_API_VERSION`
- `WHATSAPP_GRAPH_BASE_URL`
- `WHATSAPP_READINESS_MODE`
- `WHATSAPP_CONNECTIVITY_TIMEOUT_SECONDS`
- `WHATSAPP_ALERT_FAILED_SENDS_THRESHOLD`
- `WHATSAPP_ALERT_RETRIES_SCHEDULED_THRESHOLD`
- `WHATSAPP_ALERT_DLQ_GROWTH_THRESHOLD`
- `WHATSAPP_ALERT_RETRY_QUEUE_DEPTH_THRESHOLD`
- `WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS`
- `WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS`
- `WHATSAPP_WEBHOOK_MAX_BODY_BYTES`
- `WHATSAPP_SENDER_SPAM_WINDOW_SECONDS`
- `WHATSAPP_SENDER_SPAM_MAX_MESSAGES`

### 6.7 Telegram runtime

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_API_BASE_URL`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_WEBHOOK_MAX_BODY_BYTES`

### 6.8 Bootstrap/maintenance script configuration

Document and preserve script-level environment surfaces when touching the scripts that use them, including:

- `BOOTSTRAP_SEED_FILE`
- `BOOTSTRAP_FLATS_FILE`
- `BOOTSTRAP_FLATS_LIST`

---

## 7. State and permission rules

### 7.1 Event workflow rules

Current workflow action state rules:

- `DRAFT`
  - Create event.
  - Activate event.
- `ACTIVE`
  - Add/update passes.
  - Record/request payment.
  - Request refund.
  - Add expense.
  - Add sponsor contribution.
  - Refund sponsor contribution.
  - Lock passes.
- `LOCKED`
  - Record/request payment.
  - Request refund.
  - Add expense.
  - Add sponsor contribution.
  - Refund sponsor contribution.
  - Start event day.
  - Generate food tokens.
- `EVENT_DAY`
  - Generate food tokens.
  - Open food counter.
  - Serve/verify token or QR/flat lookup.
  - Record/request payment.
  - Request refund.
  - Add expense.
  - Add sponsor contribution.
  - Refund sponsor contribution.
  - Close event.
- `CLOSED`
  - Normally read-only/report-oriented.

### 7.2 Command-state policy highlights

- Non-committee active-only intents are allowed only in `ACTIVE`, `LOCKED`, or `EVENT_DAY`.
- Committee lifecycle commands are tightly state-gated:
  - `add event`, `activate event`: `DRAFT`.
  - `lock passes`: `ACTIVE`.
  - `start event`: `LOCKED`.
  - `close event`: `EVENT_DAY`.
- Food operations are state-gated:
  - `generate food tokens`: `LOCKED` or `EVENT_DAY`.
  - counter/verify/scan/serve/status/dashboard operations: `EVENT_DAY`.
- Report options, export selections, and participation reports are allowed for committee users across all event states currently listed in policy.

When adding an intent, update all applicable places together:

1. `app/channels/whatsapp/intents.py`
2. `app/commands/router.py` if detection behavior changes
3. `app/permissions/command_policy.py`
4. `app/workflows/rules.py` if the intent maps to workflow action/state rules
5. Shared handlers in `app/handlers/shared/*`
6. UI menus/handlers in `app/channels/whatsapp/ui*` if user-facing
7. i18n catalogs/templates
8. Tests and docs

---

## 8. Development rules for Codex agents

### 8.1 Required understand/plan step

Before editing code:

1. Read relevant code paths end to end.
2. Identify owning layer(s): API/channel, commands/handlers, domain module, permissions, workflow, DB, docs/tests.
3. Plan changes explicitly.
4. Avoid writing business logic in webhook/API controllers.
5. Avoid breaking public APIs, webhook contracts, or command text without updating compatibility tests/docs.

### 8.2 Architecture rules

- Keep API/webhook route handlers minimal.
- Keep channel adapters transport-specific and channel/domain boundaries clear.
- Put reusable business logic in `app/modules/*` or shared handlers as appropriate.
- Put permission/state gates in `app/permissions/*` or `app/workflows/*`; do not duplicate ad hoc checks across handlers.
- Use existing response helpers/templates and i18n catalogs for user-facing output.
- Do not mix languages in localized replies.
- Preserve audit/security logging for webhook, auth, and sensitive operations.
- Preserve idempotency, envelope persistence, retry, rate-limit, and dead-letter behavior in webhook changes.
- Never wrap imports in `try/except` blocks.

### 8.3 Documentation integrity

When implementing major architectural changes, new core modules, new database models, or new environment variables:

- Update `README.md`.
- Update relevant docs under `docs/` such as:
  - `docs/functional_workflows.md`
  - `docs/workflows.md`
  - `docs/command_access_matrix.md`
  - `docs/testing-strategy.md`
  - feature-specific docs such as announcements, food pass, or society ID docs.
- Update module-level README files when module behavior changes.
- Document new configuration and migration requirements.

---

## 9. Testing requirements

### 9.1 Full suite gate

For any code change, discover and run the full available automated test suite before finishing. If any test fails, fix it and rerun the full suite until it passes. If the environment blocks the suite, report that as a blocker and do not claim completion.

The current repository-level pytest configuration is in `pytest.ini`:

```bash
pytest
```

This runs tests under `tests/` with coverage options and coverage XML output.

### 9.2 Existing test coverage areas

The current suite includes coverage for, among others:

- API contracts and schema readiness.
- WhatsApp webhook contracts, events, runtime parity, config validation, rate limits, reliability envelope, and endpoint commands.
- Telegram integration and channel identity linking.
- Channel adapters, shared handler parity, command parser/router/policy.
- WhatsApp UI handlers, conversation/session flows, response parsing, report export service, document client behavior.
- Permissions and committee identity resolution.
- Onboarding, join/link/phone challenge flows, request code generation.
- Event service, workflow engine, food pass/collection/operations reports.
- Payments, payment requests, refunds, contributions/refunds, ledger reports.
- Report generation and report API auth.
- Announcements manager/service/dispatch/delivery worker behaviors.
- Reminder scheduler/service concurrency.
- Audit security, governance audit endpoint/report, audit retention.
- Main schema readiness, timezone awareness, localization literal guard, i18n catalog.
- Script refactor tests and smoke E2E workflow tests.

### 9.3 Marker and CI policy

Follow marker rules from `docs/testing-strategy.md`:

- Use `pytest.mark.integration` for cross-module/adaptor tests.
- Use both `pytest.mark.integration` and `pytest.mark.endpoint` for endpoint/webhook contract tests.
- Files with names containing `endpoint`, `integration`, or `webhook` require module-level markers enforced by:

```bash
python scripts/ci/check_test_markers.py
```

### 9.4 Recommended checks when relevant

In addition to `pytest`, run targeted quality checks when touching their surface:

- Localization literals:
  - `python scripts/ci/check_localization_literals.py`
- Test marker policy:
  - `python scripts/ci/check_test_markers.py`
- Mypy regression baseline:
  - `python scripts/ci/mypy_regression_guard.py`
- Smoke workflows:
  - `pytest -m smoke`

---

## 10. Success criteria for future work

A change is complete only when:

- The implementation matches the current layered architecture.
- Permissions and event-state rules are correct and centralized.
- User-facing responses use the supported language/i18n mechanisms.
- Relevant webhook/channel contract behavior is preserved.
- New models/configuration are migrated and documented.
- Full automated tests pass, or an environment blocker is clearly reported.
- Documentation stays synchronized with code.
