# Codex Master Instructions – Society Agent

You are working on a WhatsApp-based Society Management Bot.

## CONTEXT

This system includes:
- Role-based access:
  - chairman
  - secretary
  - treasurer
  - committee_member
  - non_committee_member
  - outsider

- Event states:
  - active
  - expired
  - none

- Languages:
  - English (en)
  - Hindi (hi)
  - Gujarati (gu)

The system processes incoming WhatsApp messages via webhook and returns responses based on role, event state, and language.

---

## OBJECTIVE

Fix all bugs and eliminate the need for manual testing by introducing:

1. Clean architecture
2. Automated testing
3. Full edge-case coverage
4. Reliable multilingual handling

---

## EXECUTION PHASES (STRICT)

### PHASE 1: UNDERSTAND
- Analyze entire codebase
- Identify:
  - message handling logic
  - role-based conditions
  - event-based conditions
  - language handling
- Identify tight coupling and untestable code

---

### PHASE 2: PLAN (MANDATORY)
Before writing any code:

1. Propose architecture:
   - controller (webhook)
   - service layer
   - validation layer
   - central function:

     process_message(role, message, language, event_state)

2. Define testing strategy:
   - pytest-based unit tests
   - test matrix:
     roles × event_states × languages
   - webhook payload simulation
   - edge case coverage

3. List all changes clearly

DO NOT WRITE CODE BEFORE THIS PHASE IS COMPLETE

---

### PHASE 3: IMPLEMENT
- Refactor logic into:
  services/process_message.py
- Keep webhook minimal
- Add validation layer for:
  - invalid role
  - invalid language
  - missing event

---

### PHASE 4: TEST GENERATION

Use pytest to create:

tests/test_matrix.py

Cover:

Roles:
- chairman
- secretary
- treasurer
- committee_member
- non_committee_member
- outsider

Event states:
- active
- expired
- none

Languages:
- en
- hi
- gu

Use parametrized tests.

Also test:
- invalid inputs
- empty message
- unauthorized access

---

### PHASE 5: WHATSAPP SIMULATION

Create:

tests/test_webhook_payloads.py

Simulate incoming payloads like:

{
  "role": "member",
  "message": "help",
  "language": "hi",
  "event_state": "expired"
}

Validate response correctness.

---

### PHASE 6: DEBUG LOOP

- Run all tests
- Fix failures
- Repeat until all pass

---

### PHASE 7: VALIDATION

Ensure:
- no crashes
- correct role permissions
- correct language output
- no mixed-language responses

---

### PHASE 8: OUTPUT

Provide:
1. Summary of changes
2. Bugs found and fixed
3. Test coverage details
4. Remaining risks (if any)

---

## RULES

- Do NOT skip planning
- Do NOT jump directly to coding
- Prefer simple, maintainable code
- Avoid breaking existing APIs
- Ensure all logic is testable

---

## SUCCESS CRITERIA

- All tests pass
- No manual testing required for core flows
- All combinations of role × event × language are covered
