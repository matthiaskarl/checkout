"""JSON login API for the SPA: /api/session."""

from fastapi.testclient import TestClient

from checkout.auth import SESSION_COOKIE
from checkout.models import User
from tests.conftest import PASSWORD, csrf_token_from


def test_anonymous_gets_401(client: TestClient) -> None:
    r = client.get("/api/session")
    assert r.status_code == 401
    assert r.json() == {"detail": "Not logged in"}


def test_login_returns_info_and_sets_cookie(client: TestClient, user: User) -> None:
    r = client.post("/api/session", json={"username": "Alice", "password": PASSWORD})
    assert r.status_code == 200
    info = r.json()
    assert info["username"] == "alice"
    assert len(info["csrf_token"]) >= 32
    assert "httponly" in r.headers["set-cookie"].lower()

    # The token works for writes, and GET returns the same info.
    assert client.get("/api/session").json() == info
    headers = {"X-CSRF-Token": info["csrf_token"]}
    assert client.post("/api/items", json={"name": "x"}, headers=headers).status_code == 201


def test_wrong_password(client: TestClient, user: User) -> None:
    r = client.post("/api/session", json={"username": "alice", "password": "wrong password"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid username or password."}
    assert SESSION_COOKIE not in r.cookies


def test_shared_with_jinja_login(logged_in_client: TestClient) -> None:
    """One cookie for both frontends: the Jinja2 login is visible to the API and vice versa."""
    page_token = csrf_token_from(logged_in_client.get("/ui/items/new").text)
    assert logged_in_client.get("/api/session").json()["csrf_token"] == page_token


def test_logout_needs_csrf_and_ends_session(client: TestClient, user: User) -> None:
    info = client.post("/api/session", json={"username": "alice", "password": PASSWORD}).json()
    assert client.delete("/api/session").status_code == 403
    r = client.delete("/api/session", headers={"X-CSRF-Token": info["csrf_token"]})
    assert r.status_code == 204
    assert client.get("/api/session").status_code == 401


def test_cross_site_login_blocked(client: TestClient, user: User) -> None:
    r = client.post(
        "/api/session",
        json={"username": "alice", "password": PASSWORD},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert r.status_code == 403
