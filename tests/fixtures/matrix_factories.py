import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import (
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    Event,
    Flat,
    MemberIdentity,
    Society,
    UserFlatMapping,
    WorkflowState,
)


class MatrixStateFactory:
    """
    Helper class to generate specific database states for combinatorial testing.
    """

    def __init__(self, db_session):
        self.db = db_session
        self._society = None

    def get_or_create_society(self):
        if not self._society:
            self._society = Society(
                id=uuid.uuid4(),
                name="Matrix Test Society",
                city="Test City",
                state="Test State",
                config_json={"branding": {}},
                is_active=True,
            )
            self.db.add(self._society)
            self.db.flush()
        return self._society

    def create_user_state(self, role: str, language: str, phone_number: str):
        """
        Creates a user with the specified role and language preference.
        role can be: chairman, secretary, treasurer, committee_member, non_committee, non_society
        language can be: en, hi, gu
        """
        society = self.get_or_create_society()

        identity = MemberIdentity(
            id=uuid.uuid4(),
            normalized_identifier=phone_number,
            normalized_phone=phone_number,
            preferred_language=language,
            metadata_json={"test_matrix": True},
        )
        self.db.add(identity)
        self.db.flush()

        if role == "non_society":
            self.db.commit()
            return identity, None

        flat = Flat(
            id=uuid.uuid4(),
            society_id=society.id,
            flat_number=f"A-{phone_number[-4:]}",
            block="A",
            owner_name=f"User {phone_number}",
            is_active=True,
        )
        self.db.add(flat)
        self.db.flush()

        mapping = UserFlatMapping(
            id=uuid.uuid4(),
            society_id=society.id,
            flat_id=flat.id,
            member_identity_id=identity.id,
            role="owner",
            is_active=True,
        )
        self.db.add(mapping)

        committee_member = None
        if role in ["chairman", "secretary", "treasurer", "committee_member"]:
            committee_member = CommitteeMember(
                id=uuid.uuid4(),
                society_id=society.id,
                name=f"{role.capitalize()} User",
                role=role,
                is_active=True,
                phone_number=phone_number,
            )
            self.db.add(committee_member)
            self.db.flush()

            channel_identity = CommitteeMemberChannelIdentity(
                id=uuid.uuid4(),
                committee_member_id=committee_member.id,
                channel_type="whatsapp",
                external_user_id=phone_number,
                is_verified=True,
            )
            self.db.add(channel_identity)

        self.db.commit()
        return identity, committee_member

    def create_event_state(self, event_state: str):
        """
        Supports DRAFT, ACTIVE, LOCKED, EVENT_DAY, CLOSED, and NO_EVENT
        """
        if event_state == "NO_EVENT":
            return None

        society = self.get_or_create_society()
        event = Event(
            id=uuid.uuid4(),
            society_id=society.id,
            name=f"Test Event {event_state}",
            event_date=datetime.now(timezone.utc) + timedelta(days=10),
            food_types=["veg"],
            status=event_state,
            charge_per_adult=200,
            charge_per_child=100,
        )
        self.db.add(event)
        self.db.flush()

        workflow = WorkflowState(
            id=uuid.uuid4(),
            event_id=event.id,
            current_state=event_state,
            allowed_next_states=[],
        )
        self.db.add(workflow)
        self.db.commit()
        return event
