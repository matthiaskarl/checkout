"""Test fixtures: run the app against an in-memory SQLite DB (no MySQL needed)."""

import os
import re

# Must be set before importing checkout: settings are read at import time.
# Overrides any value from .env so tests never touch the real database.
os.environ["DATABASE_URL"] = "sqlite://"

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from checkout.apikeys import create_api_key
from checkout.db import Base, get_session
from checkout.main import app
from checkout.models import User
from checkout.users import create_user

PASSWORD = "correct horse battery"


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """A fresh in-memory database per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # share one connection so the in-memory DB persists
    )

    # SQLite ignores foreign keys (incl. ON DELETE CASCADE) unless enabled per connection;
    # MySQL always enforces them. Without this, tests would be more lenient than production.
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _: Any) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """A DB session for tests of non-HTTP code (e.g. checkout.users)."""
    with session_factory() as s:
        yield s


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_session() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    # https: the session cookie is `Secure`, so (like a browser) it is only sent over HTTPS.
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user(session: Session) -> User:
    """A user 'alice' with password PASSWORD (same DB as `client`)."""
    return create_user(session, "alice", PASSWORD)


def csrf_token_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "no CSRF token in page"
    return match.group(1)


@pytest.fixture
def logged_in_client(client: TestClient, user: User) -> TestClient:
    """`client`, logged in as `user` but WITHOUT a default CSRF header (for CSRF tests)."""
    r = client.post("/ui/login", data={"username": user.username, "password": PASSWORD})
    assert r.status_code == 200, r.text  # redirect followed to the items page
    return client


@pytest.fixture
def user_client(logged_in_client: TestClient) -> TestClient:
    """Logged in, and sends the session's CSRF token on every request (like the frontends)."""
    page = logged_in_client.get("/ui/items/new").text
    logged_in_client.headers["X-CSRF-Token"] = csrf_token_from(page)
    return logged_in_client


@pytest.fixture
def api_key(session: Session, user: User) -> str:
    """A fresh API key for `user`."""
    key, _ = create_api_key(session, user, "tests")
    return key


@pytest.fixture
def key_client(client: TestClient, api_key: str) -> TestClient:
    """`client` that authenticates with an API key only (no session cookie), like a script."""
    client.headers["Authorization"] = f"Bearer {api_key}"
    return client
