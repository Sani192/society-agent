# Testing Strategy

This document defines the minimum testing policy for the repository.

## Goals

- Catch regressions early at the lowest reasonable test layer.
- Keep feedback fast for day-to-day development.
- Reserve expensive full-flow testing for only the most critical paths.

## Test Pyramid and Target Distribution

All new and existing automated tests should align with this target split:

- **70% Unit tests**
- **20% Integration tests**
- **10% End-to-end (E2E) smoke tests**

This distribution is a **portfolio target** for the suite as a whole (not every PR).

## Layer 1: Unit Tests (70%)

Use unit tests for pure logic and edge cases.

### Scope

- Stateless utility functions and pure business logic.
- Validation and normalization logic.
- Permission/rule evaluation in isolation.
- Error and boundary conditions.

### Requirements

- No network, database, queue, or cache dependencies.
- Must run quickly and deterministically.
- Cover happy path + representative edge cases.

## Layer 2: Integration Tests (20%)

Use integration tests to validate module-to-module boundaries.

### Scope

- Application modules interacting with persistence and infrastructure layers.
- DB session/model interactions.
- Queue/cache interactions.
- External adapter boundaries.

### Environment rules

- Prefer containerized dependencies (e.g., database/cache/queue) when feasible.
- External third-party services must be mocked or replaced with controlled test doubles.
- Focus on contract behavior between modules, not full user journey UX.

## Layer 3: E2E Smoke Tests (10%)

Use E2E tests only for critical user journeys.

### Scope

- A minimal set of high-value flows that prove the system can boot and execute core outcomes.
- Examples: main command/menu flow, critical submission/report flow, and one auth/permission-gated path.

### Requirements

- Keep suite intentionally small and stable.
- Run against production-like wiring where practical.
- Verify broad outcomes, not exhaustive branch coverage.

## Pull Request Minimum Required Checks

Every pull request must pass **all** of the following checks:

1. Unit test suite
2. Integration test suite
3. Smoke E2E suite

If any of these required checks fail, the PR must be marked failing and **merge is blocked** until all required checks are green.

## CI / Branch Protection Policy

- Configure CI to publish separate statuses for unit, integration, and smoke E2E jobs.
- Configure branch protection so these three statuses are required before merge.
- Do not bypass required checks except via explicit repository admin emergency procedure.
