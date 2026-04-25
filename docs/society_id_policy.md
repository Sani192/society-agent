# `society_id` denormalization policy

We are standardizing on **Option A** (`society_id` kept as a denormalized optimization) for write-heavy entities that are frequently filtered by society.

| Table | Has `event_id` | Has `flat_id` | Decision | Why |
|---|---:|---:|---|---|
| `payment_requests` | ✅ | ✅ | Keep `society_id` | Frequently scoped by society and used for request-code sequences. |
| `refund_requests` | ✅ | ✅ | Keep `society_id` | Same access pattern as payment requests. |
| `event_contributions` | ✅ | optional ✅ | Keep `society_id` | Queried in society/event reporting; `flat_id` may be null for sponsors. |
| `payment_reminders` | ✅ | ✅ | Keep `society_id` | Reminder jobs and filters are society-scoped. |

## Invariants

For the tables above:

1. `society_id` must equal `events.society_id` for the row's `event_id`.
2. When `flat_id` is present, `society_id` must equal `flats.society_id`.
3. Application write paths must derive persisted `society_id` from authoritative foreign key targets (`events`), not from caller input.

The application write paths and database-level constraints enforce these invariants to maintain consistency.
