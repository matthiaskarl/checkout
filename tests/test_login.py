"""Login/logout with server-side sessions (/ui/login, /ui/logout)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from checkout.auth import SESSION_COOKIE
from checkout.models import LoginSession, User
from checkout.sessions import utcnow
from tests.conftest import PASSWORD, csrf_token_from


def log_in(client: TestClient, username: str = "alice", password: str = PASSWORD) -> str:
    r = client.post(
        "/ui/login", data={"username": username, "password": password}, follow_redirects=False
    )
    assert r.status_code == 303, r.text
    return r.cookies[SESSION_COOKIE]


def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/ui/login")
    assert r.status_code == 200
    assert 'type="password"' in r.text


def test_login_sets_hardened_cookie(client: TestClient, user: User) -> None:
    r = client.post(
        "/ui/login", data={"username": "Alice", "password": PASSWORD}, follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith("/ui/items")
    cookie = r.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=lax", "path=/", "max-age=604800"):
        assert flag in cookie


def is_logged_in(client: TestClient) -> bool:
    return client.get("/api/items").status_code == 200


def test_logged_in_user_shown(client: TestClient, user: User) -> None:
    assert not is_logged_in(client)
    log_in(client)
    page = client.get("/ui/items/new").text
    assert "Logged in as <strong>alice</strong>" in page


@pytest.mark.parametrize(
    ("username", "password"), [("alice", "wrong password!"), ("nobody", PASSWORD)]
)
def test_failed_login_same_vague_error(
    client: TestClient, user: User, username: str, password: str
) -> None:
    r = client.post("/ui/login", data={"username": username, "password": password})
    assert r.status_code == 401
    assert "Invalid username or password." in r.text
    assert SESSION_COOKIE not in r.cookies


def test_db_stores_token_hash_only(client: TestClient, user: User, session: Session) -> None:
    token = log_in(client)
    stored = session.scalars(select(LoginSession.id)).all()
    assert len(stored) == 1
    assert stored[0] != token
    assert len(stored[0]) == 64  # sha256 hex


def test_logout_kills_session_even_for_copied_cookie(
    client: TestClient, user: User, session: Session
) -> None:
    token = log_in(client)
    csrf = csrf_token_from(client.get("/ui/items/new").text)
    r = client.post("/ui/logout", data={"csrf_token": csrf}, follow_redirects=False)
    assert r.status_code == 303
    assert session.scalars(select(LoginSession)).all() == []

    # An attacker who copied the cookie before logout can't use it any more.
    client.cookies.set(SESSION_COOKIE, token)
    assert not is_logged_in(client)


def test_relogin_replaces_old_session(client: TestClient, user: User, session: Session) -> None:
    first = log_in(client)
    client.cookies.set(SESSION_COOKIE, first)
    second = log_in(client)
    assert first != second
    assert len(session.scalars(select(LoginSession)).all()) == 1


def test_expired_session_not_accepted(client: TestClient, user: User, session: Session) -> None:
    log_in(client)
    login = session.scalars(select(LoginSession)).one()
    login.expires_at = utcnow() - timedelta(seconds=1)
    session.commit()
    assert not is_logged_in(client)


def test_deactivated_user(client: TestClient, user: User, session: Session) -> None:
    log_in(client)
    user.is_active = False
    session.commit()
    assert not is_logged_in(client)  # existing session ends
    r = client.post("/ui/login", data={"username": "alice", "password": PASSWORD})
    assert r.status_code == 401  # and no new login
