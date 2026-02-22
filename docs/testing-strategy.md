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
  - `mypy`
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
- Reliability dashboard artifacts should be retained to support pass/fail trend review and flaky cleanup work.
