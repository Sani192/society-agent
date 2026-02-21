# WhatsApp Workflow Documentation

## 1) Committee report workflow (supports closed events)
1. Committee member sends `report options`.
2. System shows:
   - Events from last 1 year (`event <number>` to select).
   - Report list (`export <number>` to export).
3. Selected event is remembered in export session.
4. Member can switch event any time with `event <number>`.
5. Sending `menu` clears remembered report session.

## 2) Invalid command workflow
1. If a WhatsApp message does not match any intent, system returns a short hint.
2. Hint now points users to valid menu options only:
   - Public: `menu`, `help`
   - Committee: `menu`, `help`, `report options`
3. `commands` intent is removed from intent map and handlers.

## 3) Help + invalid-option UX
- `help` is treated like `menu` in interactive WhatsApp webhook flow.
- Invalid option replies include a tappable **Main Menu** button (`menu`).
