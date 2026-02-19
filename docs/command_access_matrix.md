# Command Access Matrix (WhatsApp)

This matrix describes **both visibility and execution** constraints now enforced by policy.

## 1) Non-committee users

### Always available (not event-state restricted)
- `join`
- `join status`
- `help`
- `commands` (only shows allowed quick actions)
- `menu`

### Available only when event state is ACTIVE / LOCKED / EVENT_DAY
- `add pass`
- `pay`
- `refund`
- `my pass`
- `my payment requests`
- `my refund requests`
- `my payments`
- `my balance`
- `my status`
- `summary`
- `block report`

If event is `DRAFT` / `CLOSED` (or missing), these are hidden from UI lists and blocked at command execution.

## 2) Committee users (state-gated commands)

### DRAFT only
- `add event`
- `activate event`

### ACTIVE only
- `lock passes`

### LOCKED only
- `start event`

### EVENT_DAY only
- `close event`

### ACTIVE / LOCKED / EVENT_DAY
- `expense`
- `add sponsor`
- `refund sponsor`
- `remind`
- `pending payments`
- `payment requests`
- `refund requests`
- `approve payment`
- `approve refund`
- `report options`
- `export <n>` / `export::<id>`
- `participation report`

### Chairman-only (role-based, not state-gated by this policy)
- `approve user`
- `pending users`

## 3) UI visibility behavior

- Finance and Participation menus for non-committee users hide blocked state-sensitive rows.
- Reports and Administration lists are filtered so rows mapped to blocked intents are not shown in invalid event states.
- `commands` response is dynamic and only shows quick actions valid for the current event state.
