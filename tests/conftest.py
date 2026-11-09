"""Test fixtures: run the app against an in-memory SQLite DB (no MySQL needed)."""

import os

# Must be set before importing checkout: settings are read at import time.
# Overrides any value from .env so tests never touch the real database.
os.environ["DATABASE_URL"] = "sqlite://"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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


@pytest.fixture
def user_client(client: TestClient, user: User) -> TestClient:
    """`client`, already logged in as `user` (the session cookie is kept by the client)."""
    r = client.post("/ui/login", data={"username": user.username, "password": PASSWORD})
    assert r.status_code == 200, r.text  # redirect followed to the items page
    return client
