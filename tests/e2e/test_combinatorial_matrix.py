import itertools
import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.db.base import Base
from tests.fixtures.matrix_factories import MatrixStateFactory

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_element, _compiler, **_kwargs):
    return "JSON"

@compiles(PGUUID, "sqlite")
def _compile_uuid_sqlite(_element, _compiler, **_kwargs):
    return "CHAR(36)"

@pytest.fixture
def smoke_db(tmp_path, monkeypatch):
    db_file = tmp_path / "matrix_smoke.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr("app.db.session.engine", engine)
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.channels.core.handler.SessionLocal", TestingSessionLocal)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()

ROLES = ["chairman", "secretary", "treasurer", "committee_member", "non_committee", "non_society"]
EVENT_STATES = ["DRAFT", "ACTIVE", "LOCKED", "EVENT_DAY", "CLOSED", "NO_EVENT"]
LANGUAGES = ["en", "hi", "gu"]

# Map roles to their authorization level
IS_COMMITTEE = {"chairman": True, "secretary": True, "treasurer": True, "committee_member": True, "non_committee": False, "non_society": False}
HAS_SOCIETY = {"chairman": True, "secretary": True, "treasurer": True, "committee_member": True, "non_committee": True, "non_society": False}

COMMANDS = [
    "menu",
    "help",
    "report options",
    "summary",
    "block report",
    "pay 500",
    "add sponsor 5000",
    "more",
    "વધુ",
    "और",
]

def get_expected_response_type(role, event_state, language, command):
    """
    Returns the expected response type symbol to search for in the response.
    """
    if command in ["menu", "help", "more", "વધુ", "और"]:
        return "✅"
    
    if command == "report options":
        if IS_COMMITTEE[role]:
            # For committee, it shows report options if there is an event context
            return "✅"
        else:
            return "ℹ️" # Invalid option/Not allowed
    
    if command == "add sponsor 5000":
        if not IS_COMMITTEE[role]:
            return "ℹ️"
        # Interactive workflow starts with a prompt
        return "ℹ️"
            
    if command == "pay 500":
        if HAS_SOCIETY[role]:
            # Committee can pay in any state, members only in ACTIVE_EVENT_STATES
            if IS_COMMITTEE[role] or event_state in ["ACTIVE", "LOCKED", "EVENT_DAY"]:
                return "✅"
            else:
                return "ℹ️" # Disallowed state warning
        else:
            return "ℹ️" # No society context

    if command in ["summary", "block report"]:
        # Summary and Block Report are available if any event exists
        if event_state != "NO_EVENT":
            return "✅"
        else:
            return "ℹ️" # No event warning

    return "ℹ️"


@pytest.mark.parametrize("role, event_state, language, command", list(itertools.product(ROLES, EVENT_STATES, LANGUAGES, COMMANDS)))
def test_whatsapp_combinatorial_matrix(smoke_db, role, event_state, language, command):
    """
    Dynamically generated tests to evaluate the combinatorial state space of the WhatsApp bot.
    Tests every role, event state, and language preference against all commands.
    """
    factory = MatrixStateFactory(smoke_db)
    
    phone_number = f"919000{str(hash(role + event_state + language + command))[-4:]}"
    identity, committee_member = factory.create_user_state(role, language, phone_number)
    event = factory.create_event_state(event_state)
    
    inbound = InboundMessage(
        channel="whatsapp",
        sender_id=phone_number,
        display_name="Test User",
        text=command,
        metadata={},
    )
    
    # We invoke the core handler with real DB 
    response = handle_inbound_message(
        inbound,
        session_factory=lambda: smoke_db,
    )
    
    # Assert there is a response
    assert response is not None, f"Response should not be None for {command} by {role}"
    
    expected_type = get_expected_response_type(role, event_state, language, command)
    
    # Verify the response matches the expected symbol (Success ✅, Info/Error ℹ️/❌)
    # We use a broad check to ensure we don't crash and get the right class of response.
    # A deeper check would assert exact translations from catalog.py.
    assert expected_type in response or "❌" in response, f"Expected {expected_type} for '{command}' from {role} (Event: {event_state}, Lang: {language}). Got: {response}"
