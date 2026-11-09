"""CSRF protection: per-session token (form field or header) + Sec-Fetch-Site check."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, csrf_token_from

FORGED = {"name": "CSRF was here", "description": "from another origin"}


def item_names(client: TestClient) -> list[str]:
    return [item["name"] for item in client.get("/api/items").json()]


# --- layer 2: the token ---------------------------------------------------------------------


def test_form_without_token_rejected(logged_in_client: TestClient) -> None:
    """Exactly what the localhost:9000 demo page sent: cookie yes, token no."""
    r = logged_in_client.post("/ui/items/new", data=FORGED)
    assert r.status_code == 403
    assert item_names(logged_in_client) == []


def test_form_with_wrong_token_rejected(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/ui/items/new", data={**FORGED, "csrf_token": "guess"})
    assert r.status_code == 403


def test_form_with_token_accepted(logged_in_client: TestClient) -> None:
    csrf = csrf_token_from(logged_in_client.get("/ui/items/new").text)
    r = logged_in_client.post("/ui/items/new", data={"name": "Mine", "csrf_token": csrf})
    assert r.status_code == 200  # 303 followed
    assert item_names(logged_in_client) == ["Mine"]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("POST", "/api/items", {"name": "x"}), ("PATCH", "/api/items/1", {"name": "y"})],
)
def test_json_api_needs_header(
    logged_in_client: TestClient, method: str, path: str, body: dict[str, str]
) -> None:
    r = logged_in_client.request(method, path, json=body)
    assert r.status_code == 403
    assert r.json() == {"detail": "CSRF token missing or invalid"}


def test_json_api_with_header(logged_in_client: TestClient) -> None:
    csrf = csrf_token_from(logged_in_client.get("/ui/items/new").text)
    r = logged_in_client.post("/api/items", json={"name": "x"}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201


def test_reads_need_no_token(logged_in_client: TestClient) -> None:
    assert logged_in_client.get("/api/items").status_code == 200


def test_token_is_per_session(client: TestClient, logged_in_client: TestClient) -> None:
    """A token from an earlier login is useless after logging in again."""
    old = csrf_token_from(logged_in_client.get("/ui/items/new").text)
    client.post("/ui/login", data={"username": "alice", "password": PASSWORD})
    new = csrf_token_from(client.get("/ui/items/new").text)
    assert old != new
    assert (
        client.post("/api/items", json={"name": "x"}, headers={"X-CSRF-Token": old}).status_code
        == 403
    )


def test_logout_needs_token(logged_in_client: TestClient) -> None:
    """Otherwise any page could log you out (annoying, and a building block for login CSRF)."""
    assert logged_in_client.post("/ui/logout").status_code == 403


# --- layer 1: Sec-Fetch-Site ------------------------------------------------------------------


@pytest.mark.parametrize("site", ["same-site", "cross-site"])
def test_foreign_fetch_site_rejected_even_with_token(user_client: TestClient, site: str) -> None:
    r = user_client.post("/api/items", json={"name": "x"}, headers={"Sec-Fetch-Site": site})
    assert r.status_code == 403
    assert r.json() == {"detail": "Cross-origin request blocked"}


@pytest.mark.parametrize("site", ["same-site", "cross-site"])
def test_login_form_protected_by_fetch_site(client: TestClient, site: str) -> None:
    """Login CSRF: a foreign page logging you into the attacker's account."""
    r = client.post(
        "/ui/login",
        data={"username": "alice", "password": PASSWORD},
        headers={"Sec-Fetch-Site": site},
    )
    assert r.status_code == 403


@pytest.mark.parametrize("site", ["same-origin", "none", None])
def test_own_and_non_browser_requests_allowed(user_client: TestClient, site: str | None) -> None:
    headers = {"Sec-Fetch-Site": site} if site else {}
    assert user_client.post("/api/items", json={"name": "x"}, headers=headers).status_code == 201


def test_cross_site_reads_still_allowed(key_client: TestClient) -> None:
    """GETs aren't blocked by Sec-Fetch-Site, e.g. a dicesim call from another site's page."""
    r = key_client.get("/api/dicesim?goal=AB", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 200
