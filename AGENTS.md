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

# Documentation Integrity Policy
When implementing major architectural changes or new core modules:
1.  **Update READMEs**: Ensure the main `README.md` and any module-level `README.md` reflect the new design.
2.  **Sync functional docs**: Update any relevant files in `docs/` (e.g., `functional_workflows.md`) to keep the system map accurate.
3.  **Document Configuration**: Clearly document any new database models or environment variables required for the feature.

# Combinatorial Testing Policy
When implementing any new WhatsApp bot functionality, commands, or fixing related bugs, the agent MUST:
1. Update the **Combinatorial Test Matrix** located in `tests/e2e/test_combinatorial_matrix.py`.
2. Add the new command to the `COMMANDS` list and define its expected outcomes based on Role and Event State.
3. Ensure the combinatorial test suite passes fully, verifying all permutations of Roles, Event States, and Language preferences.
