# Announcement Architecture

This document describes the end-to-end flow for committee announcements.

## Goals

- Keep committee UX simple from WhatsApp menu selections.
- Support two announcement scopes:
  - **Event announcement**: only members who are fully paid for that event.
  - **Society announcement**: all active members in the society.
- Ensure **policy-safe WhatsApp delivery** (template-only, throttled, retry-aware).
- Keep dispatch asynchronous and auditable.

## Command UX (unchanged)

Committee options remain available from menu:

- `announce event`
- `announce society`

Flow:
1. Committee taps a menu option.
2. If no free text is provided in same message, bot asks for message body.
3. Committee sends free text.
4. System queues announcement and acknowledges:
   - accepted targets
   - skipped targets
   - announcement ID

## High-level module design

### 1) Orchestration layer

`app/modules/announcements/manager.py`

- `AnnouncementManager.queue(...)` orchestrates scope-specific behavior.
- Resolves recipients via `AnnouncementRecipientService`.
- Persists announcement + deliveries via `AnnouncementService`.
- Triggers async dispatch worker (`run_pending_announcement_deliveries`) in daemon thread.

This keeps committee handler thin and avoids embedding recipient/query logic directly in command handling.

### 2) Recipient resolution

`app/modules/announcements/recipient_service.py`

- `get_event_joined_member_targets(...)`
  - joins payment/member mapping tables
  - includes only `Payment.status == "paid"`
  - deduplicates by WhatsApp ID
- `get_active_member_targets(...)`
  - includes only active user-flat mappings
  - deduplicates by WhatsApp ID

Resolver output includes:
- `targets`
- `total_candidates`
- `queued_count`
- `skipped_missing_whatsapp`
- `duplicate_whatsapp_ids`

### 3) Persistence + template rendering

`app/modules/announcements/service.py`

- `create_announcement(...)` writes:
  - `announcements`
  - `announcement_deliveries`
- `build_whatsapp_template_payload(...)` creates rendered payload per recipient:
  - society: `society_announcement_general` with `[receiver_name, free_text]`
  - event: `society_announcement_event` with `[receiver_name, event_name, free_text]`
- `ensure_whatsapp_template_delivery(...)` enforces template-only announcement delivery on WhatsApp.

### 4) Delivery worker

`app/modules/announcements/delivery_worker.py`

- Pulls pending deliveries in batches.
- Uses template sends only (`send_template_message`).
- Applies rate protections:
  - max sends per batch
  - per-minute throttling
  - inter-send interval
- Applies retry protections:
  - retryable HTTP statuses (429/5xx)
  - exponential backoff
  - `Retry-After` support via `WhatsAppRetryableError`
- Applies circuit breaker when error rate crosses threshold.
- Updates aggregate summary fields on `announcements` after each outcome.

## Policy posture

For announcements, all WhatsApp deliveries are template-based.

This guarantees consistent recipient experience and avoids mixed-mode behavior where some users receive free text while others receive templates.

## Data model

### `announcements`
- `id`, `society_id`, `event_id`, `type`, `message_text`, `created_by`
- summary fields: `total_targets`, `sent_count`, `failed_count`, `skipped_count`

### `announcement_deliveries`
- composite key: `announcement_id`, `member_identity_id`, `channel`
- `recipient_id`, `rendered_payload`, `status`, `attempts`, `last_error`, `sent_at`

## Committee handler integration

`app/handlers/shared/committee.py`

- Handles `ANNOUNCE_EVENT` and `ANNOUNCE_SOCIETY` intents.
- Validates body length and non-empty input.
- Delegates queueing to `AnnouncementManager.queue(...)`.
- Returns acknowledgement message with queue metrics.

## Testing map

- `tests/test_committee_handler.py`
  - command behavior and prompt/validation/ack flows
- `tests/test_announcement_service.py`
  - template payload validation and persistence behavior
- `tests/test_announcement_delivery_worker.py`
  - policy checks and template send behavior
- `tests/test_announcement_dispatch_behaviors.py`
  - retry/backoff/idempotency/segmentation behaviors

