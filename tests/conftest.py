import os

# Minimal values for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("HOST", "http://testserver")

# If your Settings requires these R2 fields, set harmless dummies:
os.environ.setdefault("CLOUDFLARE_R2_ACCESS_KEY_ID", "dummy")
os.environ.setdefault("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "dummy")
os.environ.setdefault("CLOUDFLARE_R2_BUCKET_NAME", "dummy-bucket")
os.environ.setdefault("CLOUDFLARE_S3_URL", "http://localhost")
import asyncio

from httpx import ASGITransport
from httpx import AsyncClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventcloud.app import app
from eventcloud.auth.deps import current_user
from eventcloud.db import Base
from eventcloud.db import get_db
from eventcloud.models import Event
from eventcloud.models import EventMessage


# ---- pytest-asyncio event loop (safe for >=0.23) ----
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine():
    # Create an in-memory SQLite database for testing, or connect to a test database
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(test_engine)  # Create tables
    yield test_engine
    Base.metadata.drop_all(test_engine)  # Drop tables after tests


@pytest.fixture(scope="function")
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()  # Rollback changes to keep the database clean for next test
    connection.close()


# ---- Override get_db to yield our test session ----
@pytest.fixture(autouse=True)
def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


# ---- Override auth dependency so the route runs ----
@pytest.fixture(autouse=True)
def override_current_user():
    class FakeUser:
        id = 1
        email = "test@example.com"
        is_staff = True

    app.dependency_overrides[current_user] = lambda: FakeUser()
    yield
    app.dependency_overrides.pop(current_user, None)


# ---- HTTP client bound to the ASGI app ----
@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---- BeautifulSoup helper ----
@pytest.fixture
def soup():
    from bs4 import BeautifulSoup

    return lambda html: BeautifulSoup(html, "html.parser")


@pytest.fixture
def sample_events(session):
    events = [Event(title=f"Event {i + 1}", code=f"code{i + 1}") for i in range(5)]
    session.add_all(events)
    session.commit()
    return events


@pytest.fixture
def single_event(session):
    event = Event(title="Test Event", code="test123")
    session.add(event)
    session.commit()
    return event


@pytest.fixture
def normal_messages_for_single_event(session, single_event):
    messages = [
        EventMessage(event_id=single_event.code, text=f"Normal Message {x}", pinned=False)
        for x in range(0, 5)
    ]
    session.add_all(messages)
    session.commit()
    return messages


@pytest.fixture
def pinned_messages_for_single_event(session, single_event):
    messages = [
        EventMessage(event_id=single_event.code, text=f"Pinned Message {x}", pinned=True)
        for x in range(0, 5)
    ]
    session.add_all(messages)
    session.commit()
    return messages


@pytest.fixture
def all_messages_for_single_event(
    normal_messages_for_single_event, pinned_messages_for_single_event
):
    return normal_messages_for_single_event + pinned_messages_for_single_event
