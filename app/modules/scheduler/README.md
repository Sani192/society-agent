# Unified Database-Driven Scheduler

This module provides a production-ready, industry-standard scheduling architecture. It consolidates multiple disjointed schedulers into a single, robust system that is fully configurable via the database.

## Architecture

The system uses a `BackgroundScheduler` (from `APScheduler`) managed by the `SchedulerManager`.

### Key Components

- **`SchedulerManager`**: A synchronization loop that polls the `periodic_tasks` table every 30 seconds. It dynamically adds, updates, or removes jobs in the in-memory scheduler based on the database state.
- **`PeriodicTask` Model**: The single source of truth for all scheduled jobs.
- **Task Wrapper**: A standardized execution wrapper that handles database session management, error logging, and updates task execution metadata (`last_run_at`, `total_runs`).
- **Leader Election**: Uses PostgreSQL advisory locks (`pg_try_advisory_lock`) to ensure that only one worker instance acts as the "Leader" and runs the scheduler in a multi-node deployment.

## Configuration

All tasks are configured in the `periodic_tasks` database table.

### Task Fields

| Field | Description |
|---|---|
| `name` | Unique identifier for the task. |
| `task_function` | Full python path to the function (e.g., `app.modules.reminders.reminder_scheduler.run_payment_reminders`). |
| `kwargs_json` | JSON object containing arguments passed to the task function. |
| `schedule_type` | `interval` or `cron`. |
| `interval_seconds` | Required if `schedule_type` is `interval`. |
| `cron_hour` | Hour(s) for cron trigger (0-23 or `*`). |
| `cron_minute` | Minute(s) for cron trigger (0-59 or `*`). |
| `enabled` | Boolean flag to toggle the task. |

### Available Schedulers (Default Tasks)

1. **`payment_reminders`**: Sends automated WhatsApp reminders for pending payments.
   - Target: `app.modules.reminders.reminder_scheduler.run_payment_reminders`
   - Default: `cron` at 10:00 daily.
2. **`event_auto_close`**: Automatically moves events from `EVENT_DAY` to `CLOSED` after a certain age.
   - Target: `app.modules.reminders.reminder_scheduler.run_event_auto_close_job`
   - Default: `cron` at 10:00 daily.
3. **`audit_retention_prune`**: Prunes old audit logs based on retention policy.
   - Target: `app.modules.reminders.reminder_scheduler.run_audit_retention_prune`
   - Default: `cron` at 03:15 daily.
4. **`announcement_delivery_dispatch`**: Dispatches pending announcement messages in batches.
   - Target: `app.modules.announcements.delivery_worker.run_pending_announcement_deliveries`
   - Default: `interval` every 30 seconds.

## How to add a new task

1.  **Implement the function**: Create a function in the appropriate module. It should accept `**kwargs` if you plan to pass arguments via `kwargs_json`.
2.  **Add to database**: Insert a new row into the `periodic_tasks` table.
    ```sql
    INSERT INTO periodic_tasks (name, task_function, schedule_type, interval_seconds, enabled)
    VALUES ('my_new_task', 'app.modules.my_module.tasks.my_func', 'interval', 60, true);
    ```
3.  **Sync**: The `SchedulerManager` will automatically pick up the new task within 30 seconds.

## Global Disable

You can disable the entire scheduler functionality globally by setting the `SCHEDULER_ENABLED` environment variable:
- `SCHEDULER_ENABLED=false`: The `SchedulerManager` will skip startup and no tasks will run.
- `SCHEDULER_ENABLED=true` (default): Normal operation.

## Operations

- **Start Scheduler**: `python scripts/run_scheduler.py`
- **Seed Defaults**: `python scripts/seed_periodic_tasks.py`
- **Disable a task**: Set `enabled = false` in the database. No restart required.
- **Change timing**: Update the cron/interval fields in the database. No restart required.
