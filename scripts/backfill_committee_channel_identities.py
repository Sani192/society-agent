#!/usr/bin/env python3

from pathlib import Path
import sys


def run() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.db.models import CommitteeMember, CommitteeMemberChannelIdentity
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        members = (
            db.query(CommitteeMember)
            .filter(CommitteeMember.is_active.is_(True), CommitteeMember.phone_number.isnot(None))
            .all()
        )

        created = 0
        for member in members:
            has_whatsapp_identity = (
                db.query(CommitteeMemberChannelIdentity)
                .filter(
                    CommitteeMemberChannelIdentity.committee_member_id == member.id,
                    CommitteeMemberChannelIdentity.channel_type == "whatsapp",
                )
                .first()
                is not None
            )
            if has_whatsapp_identity:
                continue

            db.add(
                CommitteeMemberChannelIdentity(
                    committee_member_id=member.id,
                    channel_type="whatsapp",
                    external_user_id=member.phone_number,
                    username=None,
                    is_verified=True,
                )
            )
            created += 1

        db.commit()
        print(f"Backfilled {created} missing WhatsApp channel identities for active committee members.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
