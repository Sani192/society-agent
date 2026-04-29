import importlib
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.models import PeriodicTask
from app.utils.logger import logger
from app.config import settings

unified_scheduler = BackgroundScheduler()

# In-memory dictionary to track task hashes and avoid recreating unchanged jobs
_task_hashes: dict[str, int] = {}

def acquire_scheduler_leader_lock(lock_key: int = 937450):
    """Acquire and hold a session-scoped PostgreSQL advisory lock."""
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": lock_key})
        if bool(result.scalar()):
            return db
        db.close()
        return None
    except Exception:
        logger.exception("Failed to acquire scheduler advisory lock")
        db.close()
        return None


def resolve_task_function(task_function_path: str):
    module_path, func_name = task_function_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def task_wrapper(task_id: str, task_function_path: str, kwargs_json: dict):
    func = resolve_task_function(task_function_path)
    try:
        func(**kwargs_json)
    except Exception:
        logger.exception(f"Error executing scheduled task {task_function_path}")
    finally:
        db = SessionLocal()
        try:
            task = db.query(PeriodicTask).filter(PeriodicTask.id == task_id).first()
            if task:
                setattr(task, "last_run_at", datetime.now(timezone.utc))
                current_runs = int(getattr(task, "total_runs", 0) or 0)
                setattr(task, "total_runs", current_runs + 1)
                db.commit()
        except Exception:
            logger.exception("Error updating periodic task stats")
            db.rollback()
        finally:
            db.close()


def _get_task_hash(task: PeriodicTask) -> int:
    return hash((
        task.task_function,
        str(task.kwargs_json),
        task.schedule_type,
        task.interval_seconds,
        task.cron_minute,
        task.cron_hour,
        task.cron_day,
        task.cron_month,
        task.cron_day_of_week
    ))


def sync_periodic_tasks():
    db = SessionLocal()
    try:
        tasks = db.query(PeriodicTask).all()
        active_task_ids = set()

        for task in tasks:
            if not task.enabled:
                if str(task.id) in _task_hashes:
                    del _task_hashes[str(task.id)]
                continue

            job_id = str(task.id)
            active_task_ids.add(job_id)
            
            current_hash = _get_task_hash(task)
            if _task_hashes.get(job_id) == current_hash and unified_scheduler.get_job(job_id):
                continue

            trigger_kwargs = {}
            if task.schedule_type == 'interval':
                trigger_kwargs = {'trigger': 'interval', 'seconds': task.interval_seconds}
            elif task.schedule_type == 'cron':
                trigger_kwargs = {
                    'trigger': 'cron',
                    'minute': task.cron_minute,
                    'hour': task.cron_hour,
                    'day': task.cron_day,
                    'month': task.cron_month,
                    'day_of_week': task.cron_day_of_week
                }
                trigger_kwargs = {k: v for k, v in trigger_kwargs.items() if v is not None}
            else:
                logger.warning(f"Unknown schedule type {task.schedule_type} for task {task.name}")
                continue

            args = [str(task.id), task.task_function, task.kwargs_json or {}]

            unified_scheduler.add_job(
                task_wrapper,
                args=args,
                id=job_id,
                replace_existing=True,
                **trigger_kwargs
            )
            _task_hashes[job_id] = current_hash
            logger.info(f"Loaded/Updated scheduled task: {task.name}")

        # Remove jobs that are no longer active or enabled
        for job in unified_scheduler.get_jobs():
            if job.id != 'sync_periodic_tasks' and job.id not in active_task_ids:
                unified_scheduler.remove_job(job.id)
                if job.id in _task_hashes:
                    del _task_hashes[job.id]
                logger.info(f"Removed scheduled task: {job.id}")

    except Exception:
        logger.exception("Failed to sync periodic tasks")
    finally:
        db.close()


def start_scheduler_manager():
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled via settings (SCHEDULER_ENABLED=false). Skipping startup.")
        return

    # Sync periodically
    unified_scheduler.add_job(
        sync_periodic_tasks,
        trigger='interval',
        seconds=30,
        id='sync_periodic_tasks',
        replace_existing=True
    )

    # Initial sync
    sync_periodic_tasks()

    unified_scheduler.start()
    logger.info("Unified database-driven scheduler manager started.")
