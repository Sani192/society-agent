# Testing Strategy

This document defines the minimum testing and CI reliability policy for the repository.

## Goals

- Catch regressions early at the lowest reasonable test layer.
- Keep feedback fast for day-to-day development.
- Reserve expensive full-flow testing for only the most critical paths.
- Track pass/fail health and flaky behavior as first-class reliability signals.

## Test Pyramid and Target Distribution

All new and existing automated tests should align with this target split:

- **70% Unit tests**
- **20% Integration tests**
- **10% End-to-end (E2E) smoke tests**

This distribution is a **portfolio target** for the suite as a whole (not every PR).

## CI Stages

### Stage 1 (minutes): lint + type checks + fast unit tests

- Runs on every PR.
- Runs:
  - `ruff check`
  - repo-wide `mypy` regression guard (`app`, `scripts`) against committed baseline
  - fast unit tests (`pytest -m "not integration and not endpoint and not smoke"`)
- Uses `pytest-testmon` cache to run impacted tests where possible.

### Stage 2: integration + endpoint tests

- Runs after Stage 1 on every PR.
- Runs `pytest -m "integration or endpoint"`.
- Uses `pytest-testmon` for impact selection and `pytest-rerunfailures` to surface flaky candidates.

### Stage 3: E2E policy

- **PRs:** always run critical smoke (`pytest -m smoke`) even if impact selection reduces earlier suites.
- **Nightly + release branches:** run full E2E regression (`pytest tests/e2e`) and contract drift checks.

## Test Impact Selection Policy

- Default to impact-aware execution through `pytest-testmon` in Stage 1 and Stage 2.
- If no historical test impact cache is available, suites fall back to broader execution.
- Impact selection is an optimization only; it must never suppress critical smoke coverage.

## Type Safety Baseline Policy

- CI runs repo-wide mypy and compares findings with `ci/mypy-baseline.txt`.
- PRs fail when **new** type errors are introduced.
- When errors are fixed, baseline should be reduced accordingly in the same PR.


## Marker Assignment Policy

Markers are mandatory for tests that validate API/webhook entry points or multi-module integration behavior.

- Add `pytestmark = [pytest.mark.integration]` for tests that cross module boundaries, exercise adapters, or run behavior that is not pure unit logic.
- Add `pytestmark = [pytest.mark.integration, pytest.mark.endpoint]` for tests that validate handler/webhook endpoint contracts (request parsing, auth/signature checks, response contracts).
- Files in `tests/test_*.py` with names containing `endpoint`, `integration`, or `webhook` are required to include a module-level `pytestmark` declaration with at least one of these markers.
- CI enforces this through `python scripts/ci/check_test_markers.py`.

Examples:

- `tests/test_whatsapp_endpoint_commands.py` → `pytestmark = [pytest.mark.integration, pytest.mark.endpoint]`
- `tests/test_whatsapp_webhook_event.py` → `pytestmark = [pytest.mark.integration, pytest.mark.endpoint]`
- `tests/test_telegram_integration.py` → `pytestmark = [pytest.mark.integration, pytest.mark.endpoint]`

## Reliability Standards and Dashboards

- Every pipeline publishes JUnit XML and a generated reliability dashboard artifact.
- The dashboard summarizes:
  - total/passed/failed/skipped counts
  - suite pass rates
  - flaky test candidates (rerun/flaky signals from JUnit)
- Flaky thresholds are enforced in CI:
  - PR smoke: zero known flaky candidates allowed
  - Nightly/release regression: small temporary budget (configured threshold)

## Pull Request Minimum Required Checks

Every pull request must pass **all** of the following checks:

1. Stage 1 (lint, type checks, fast unit)
2. Stage 2 (integration + endpoint)
3. Stage 3 (critical smoke E2E)

If any required check fails, PR merge is blocked.

## CI / Branch Protection Policy

- Configure branch protection to require all three PR stages.
- Do not bypass required checks except via explicit repository admin emergency procedure.
## Combinatorial Testing Policy

To avoid the combinatorial explosion of manual testing across various user roles, event states, and languages, the repository uses a **Matrix-based Integration Testing** approach.

### Goal
Systematically verify every permutation of:
- **Roles**: Chairman, Secretary, Treasurer, Committee Member, Non-Committee, Non-Society.
- **Event States**: DRAFT, ACTIVE, LOCKED, EVENT_DAY, CLOSED, No Event.
- **Languages**: English (en), Hindi (hi), Gujarati (gu).
- **Core Commands**: menu, help, pay, refund, summary, etc.

### Implementation
- Tests are located in `tests/e2e/test_combinatorial_matrix.py`.
- They use the `MatrixStateFactory` to generate a fresh, isolated database state for every permutation.
- They exercise the full `handle_inbound_message` entry point to ensure all middleware, resolvers, and handlers are tested in unison.

### Enforcement
- **Mandatory for completion**: Agents must ensure the full combinatorial suite passes before finishing any feature work related to bot commands or permissions.
- **Matrix Updates**: Any new command or permission logic MUST be added to the `COMMANDS` list and the `get_expected_response_type` mapping in the matrix test suite.

