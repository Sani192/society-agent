# Agent Execution Policy (Repository Scope)

When making **any code change** in this repository, the agent must follow this gate before finishing:

1. Discover and run the **full available automated test suite** for the repository (not only targeted tests).
2. If **any** test fails, do **not** finish the task as complete.
3. Fix failures and re-run the full suite until all tests pass.
4. Only then provide final completion output.

Clarifications:
- This rule applies whether or not the user explicitly asks to run tests.
- Running only a subset of tests is not sufficient for completion after code changes.
- If the environment blocks running tests (missing system dependency, service outage, etc.), report it as a blocker and do not claim task completion.
