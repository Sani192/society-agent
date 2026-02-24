#!/usr/bin/env python3

from pathlib import Path
import sys

from sqlalchemy import text


def _has_table(conn, table_name: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    return row is not None


def run():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS member_identities (
                id TEXT PRIMARY KEY,
                normalized_identifier TEXT NOT NULL UNIQUE,
                normalized_phone TEXT,
                whatsapp_user_id TEXT UNIQUE,
                telegram_user_id TEXT UNIQUE,
                metadata_json JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_member_identities_normalized_identifier ON member_identities(normalized_identifier)"))

        has_mappings = _has_table(conn, "user_flat_mappings")
        has_pending = _has_table(conn, "pending_users")

        if has_mappings or has_pending:
            union_parts = []
            if has_mappings:
                union_parts.append("SELECT DISTINCT user_identifier FROM user_flat_mappings")
            if has_pending:
                union_parts.append("SELECT DISTINCT user_identifier FROM pending_users")
            union_sql = " UNION ".join(union_parts)

            conn.execute(text(
                f"""
                INSERT INTO member_identities (id, normalized_identifier, normalized_phone, metadata_json)
                SELECT lower(hex(randomblob(16))), user_identifier, user_identifier, json('{{"backfilled": true}}')
                FROM ({union_sql}) src
                WHERE user_identifier IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM member_identities mi WHERE mi.normalized_identifier = src.user_identifier
                  )
                """
            ))

        for table in ("user_flat_mappings", "pending_users", "payment_requests", "refund_requests"):
            if not _has_table(conn, table):
                continue
            cols = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            if "member_identity_id" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN member_identity_id TEXT"))

        if has_mappings:
            conn.execute(text(
                """
                UPDATE user_flat_mappings
                SET member_identity_id = (
                    SELECT id FROM member_identities mi
                    WHERE mi.normalized_identifier = user_flat_mappings.user_identifier
                    LIMIT 1
                )
                WHERE member_identity_id IS NULL
                """
            ))

        if has_pending:
            conn.execute(text(
                """
                UPDATE pending_users
                SET member_identity_id = (
                    SELECT id FROM member_identities mi
                    WHERE mi.normalized_identifier = pending_users.user_identifier
                    LIMIT 1
                )
                WHERE member_identity_id IS NULL
                """
            ))

        if _has_table(conn, "payment_requests") and has_mappings:
            conn.execute(text(
                """
                UPDATE payment_requests
                SET member_identity_id = (
                    SELECT ufm.member_identity_id FROM user_flat_mappings ufm
                    WHERE ufm.id = payment_requests.requested_by_mapping_id
                    LIMIT 1
                )
                WHERE member_identity_id IS NULL
                """
            ))

        if _has_table(conn, "refund_requests") and has_mappings:
            conn.execute(text(
                """
                UPDATE refund_requests
                SET member_identity_id = (
                    SELECT ufm.member_identity_id FROM user_flat_mappings ufm
                    WHERE ufm.id = refund_requests.requested_by_mapping_id
                    LIMIT 1
                )
                WHERE member_identity_id IS NULL
                """
            ))

        print("Backfill complete. Validate counts before dropping legacy columns.")


if __name__ == "__main__":
    run()
