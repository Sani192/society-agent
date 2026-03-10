# Digital Food Pass Workflow

This document explains the **end-to-end digital food pass workflow** currently implemented in the system: roles, commands, event-stage behavior, token collection/distribution, and day-of serving operations.

---

## 1) What the digital food pass system does

The workflow supports:

- Pass booking per flat (veg/jain/kids counts)
- Automatic expected payment calculation
- Member payment and payment-request flow
- Token generation (one token per plate)
- Member token visibility (`my tokens`)
- Event-day serving at food counters by token/QR/flat lookup
- Committee dashboard for live serving progress

Core services:

- `FoodPassService` for pass add/update and opt-out
- `FoodCollectionService` for token lifecycle + serving
- Committee/Public handlers for WhatsApp command UX

---

## 2) Roles and who can do what

## Non-committee members

Typical member capabilities:

- Add/update own pass (`add pass ...`)
- View own pass (`my pass`)
- View own tokens (`my tokens`)
- Pay/request payment (`pay ...`) depending on identity context
- Request refund (`refund ...`) depending on identity context

Members are restricted by event state policy for active-only actions.

## Committee members

Committee capabilities include member actions plus operations:

- Generate food tokens
- Open food counter
- Verify/serve token manually
- Scan QR token
- Serve using flat lookup fallback
- Check flat pass status / token status
- View food dashboard

Additional role restrictions apply for broader event lifecycle actions (activate/lock/start/close), but food operations are exposed to committee command flows.

---

## 3) Event stages that affect food pass behavior

The platform event states are:

- `DRAFT`
- `ACTIVE`
- `LOCKED`
- `EVENT_DAY`
- `CLOSED`

Member-facing state gating enforces many commands only when event is active (ACTIVE/LOCKED/EVENT_DAY from policy definitions for active event states).

Typical practical sequence:

1. Event created and activated
2. Members add/update passes
3. Committee locks passes / starts event day
4. Committee generates tokens and opens counter
5. Serving happens via token scan/manual/flat lookup
6. Dashboard/status commands track execution

---

## 4) Member workflow (non-committee UX)

## Step 1: Book or update pass

Command pattern:

- `add pass veg 2 jain 1 kid 1`

Behavior:

- Parses counts for `veg`, `jain`, `kids`
- Requires at least one total person
- Calculates total amount using event pricing
- Creates/updates one pass record for the member flat
- Creates/updates payment expectation (`Payment.expected_amount`)

Output:

- Success confirmation with Veg/Jain/Kids counts

## Step 2: View pass summary

Command:

- `my pass`

Behavior:

- Shows pass counts
- Shows served/remaining summary by type if tokens exist
- Suggests `my tokens` for detailed token list

## Step 3: View individual tokens

Command:

- `my tokens`

Behavior:

- Shows all generated tokens for the member flat
- Shows token-level status (Served/Pending)
- Shows per-type totals and remaining

If tokens are not generated yet, user is told to wait for committee update.

## Step 4: Payments

Command:

- `pay 500`

Behavior depends on context:

- Non-committee identity path creates a **payment request** for approval
- Committee path can directly process payment/approve matching request

Food pass expected amount is used for payment validation/status updates.

## Step 5: Opt-out scenario

Members/committee can mark not participating through service paths; pass counts become zero and participation false.

---

## 5) Committee workflow (operations)

## A) Generate tokens

Command:

- `generate food tokens`

What it does:

- Generates one token per booked plate across all participating passes
  - Veg count => veg tokens
  - Jain count => jain tokens
  - Kids count => kids tokens
- Token code format: random uppercase alnum from constrained alphabet
- Prevents regeneration if tokens already exist for event
- Creates audit entry
- Sends token notifications callback where configured

Outcome message includes generated token count and reminds members to use `my tokens`.

## B) Open food counter

Command:

- `open food counter` (default 120 min)
- `open food counter 60` (custom auto-close minutes)

What it does:

- Opens/updates event food counter
- Stores open time and `closes_at`
- Queues an event announcement to members with closing time

## C) Serve plate using token/QR/manual

Commands:

- `verify food token AB2K9M` (manual token entry)
- `scan food qr AB2K9M` (QR equivalent token path)

Validation path:

- Method must be valid (`MANUAL_TOKEN` / `QR_SCAN` / `FLAT_LOOKUP`)
- Event must exist
- Counter must be open and not expired
- Token must exist for event
- Token must be unused

If valid:

- Marks token as served (`served_at`, `served_method`, `served_by`)
- Writes audit entry

If invalid:

- Rejects with explicit error (invalid token/already used/counter closed/service ended)
- Audit entry for rejection scenarios

## D) Serve by flat lookup fallback

Command:

- `serve flat A-101`

Behavior:

1. Attempts first unserved token for flat (FIFO by token create time)
2. If no unserved token exists, checks entitlement vs served counts
3. If entitlement remains, allows no-token fallback serve and audits `FLAT_LOOKUP_NO_TOKEN`
4. If no entitlement remains, rejects

This supports practical counter operations when a resident forgets token/QR.

## E) Status and dashboard checks

Commands:

- `flat passes A-101` -> per-flat total/served/remaining
- `token status AB2K9M` -> token state
- `food dashboard` -> total served/remaining + by-type + recent served list

These are used by committee during live operations.

---

## 6) Interactive UI shortcuts (WhatsApp list/menu flows)

Beyond free-text commands, WhatsApp UI routing supports list-driven actions for:

- Verify token
- Scan token
- Token status
- Serve flat
- Flat pass status

This improves usability for committee members by reducing typing and command mistakes.

---

## 7) Supported command quick reference

## Member-facing

- `add pass veg <n> jain <n> kid <n>`
- `my pass`
- `my tokens`
- `pay <amount>`
- `refund <amount> reason <text>`

## Committee food operations

- `generate food tokens`
- `open food counter [minutes]`
- `verify food token <TOKEN>`
- `scan food qr <TOKEN>`
- `serve flat <FLAT_NUMBER>`
- `flat passes <FLAT_NUMBER>`
- `token status <TOKEN>`
- `food dashboard`

---

## 8) User-friendliness notes

For non-committee members:

- Straightforward “self-service” flow (`add pass`, `my pass`, `my tokens`, `pay`)
- Clear text responses and guided examples when parameters are missing

For committee members:

- Full operational command set for event day
- Menu/list-based picker support in WhatsApp
- Realtime dashboard and token/flat diagnostics
- Auto-close counter and announcement support

---

## 9) Practical end-to-end example

1. Member sends: `add pass veg 2 jain 1 kid 1`
2. System stores pass + expected payment
3. Committee sends: `generate food tokens`
4. Members send: `my tokens` to view token list
5. Committee sends: `open food counter 90`
6. At counter:
   - Scan/verify token to serve each plate
   - If token missing: `serve flat A-101`
7. Committee monitors `food dashboard` and `flat passes A-101`

This is the implemented digital collection + distribution workflow today.
