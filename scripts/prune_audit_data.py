#!/usr/bin/env python3
from app.db.session import SessionLocal
from app.modules.audit.retention_service import AuditRetentionService
from app.utils.logger import logger


def main() -> int:
    db = SessionLocal()
    try:
        deleted = AuditRetentionService.prune(db)
        logger.info("Audit prune completed from CLI | deleted=%s", deleted)
        print(deleted)
        return 0
    except Exception:
        db.rollback()
        logger.exception("Audit prune failed from CLI")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
