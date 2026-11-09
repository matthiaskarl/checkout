"""Which routes need a login, and what anonymous callers get back."""

import pytest
from fastapi.testclient import TestClient

from checkout.models import User
from tests.conftest import PASSWORD


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/items"),
        ("POST", "/api/items"),
        ("GET", "/api/items/1"),
        ("PATCH", "/api/items/1"),
        ("DELETE", "/api/items/1"),
    ],
)
def test_api_requires_login(client: TestClient, method: str, path: str) -> None:
    r = client.request(method, path, json={"name": "x"})
    assert r.status_code == 401  # 401 before validation/404: anonymous callers learn nothing
    assert r.json() == {"detail": "Not logged in"}


def test_page_redirects_to_login_with_next(client: TestClient) -> None:
    r = client.get("/ui/items/new?created=3", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == (
        "https://testserver/ui/login?next=%2Fui%2Fitems%2Fnew%3Fcreated%3D3"
    )


def test_anonymous_post_to_page_creates_nothing(client: TestClient, user: User) -> None:
    r = client.post("/ui/items/new", data={"name": "sneaky"}, follow_redirects=False)
    assert r.status_code == 303
    client.post("/ui/login", data={"username": "alice", "password": PASSWORD})
    assert client.get("/api/items").json() == []


def test_login_returns_to_next(client: TestClient, user: User) -> None:
    login_page = client.get("/ui/items/new?created=3")  # follows the redirect
    assert 'name="next" value="/ui/items/new?created=3"' in login_page.text

    r = client.post(
        "/ui/login",
        data={"username": "alice", "password": PASSWORD, "next": "/ui/items/new?created=3"},
        follow_redirects=False,
    )
    assert r.headers["location"] == "/ui/items/new?created=3"


@pytest.mark.parametrize(
    "evil", ["https://evil.example/", "//evil.example/", "/\\evil.example/", "javascript:x"]
)
def test_login_ignores_foreign_next(client: TestClient, user: User, evil: str) -> None:
    r = client.post(
        "/ui/login",
        data={"username": "alice", "password": PASSWORD, "next": evil},
        follow_redirects=False,
    )
    assert r.headers["location"] == "https://testserver/ui/items/new"


@pytest.mark.parametrize("path", ["/api/health", "/api/docs", "/api/dicesim?goal=AB", "/ui/login"])
def test_public_routes(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200
