"""The Jinja2 admin UI: list page, delete (plain form and htmx), layout pieces."""

from fastapi.testclient import TestClient

from tests.conftest import csrf_token_from


def create(client: TestClient, name: str) -> int:
    r = client.post("/api/items", json={"name": name, "description": f"about {name}"})
    assert r.status_code == 201
    item_id: int = r.json()["id"]
    return item_id


def test_ui_root_redirects_to_list(user_client: TestClient) -> None:
    r = user_client.get("/ui/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith("/ui/items")


def test_list_newest_first(user_client: TestClient) -> None:
    create(user_client, "Teapot")
    create(user_client, "Kettle")
    page = user_client.get("/ui/items").text
    assert page.index("Kettle") < page.index("Teapot")
    assert 'hx-confirm="Delete item #1 (Teapot)?"' in page


def test_list_empty(user_client: TestClient) -> None:
    assert "No items yet." in user_client.get("/ui/items").text


def test_list_requires_login(client: TestClient) -> None:
    r = client.get("/ui/items", follow_redirects=False)
    assert r.status_code == 303
    assert "/ui/login?next=%2Fui%2Fitems" in r.headers["location"]


def test_delete_plain_form(logged_in_client: TestClient) -> None:
    """Without JavaScript: form POST with the hidden field, redirect back with a notice."""
    csrf = csrf_token_from(logged_in_client.get("/ui/items").text)
    item_id = create_with_token(logged_in_client, csrf, "Teapot")
    r = logged_in_client.post(
        f"/ui/items/{item_id}/delete", data={"csrf_token": csrf}, follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/ui/items?deleted={item_id}")
    page = logged_in_client.get(r.headers["location"]).text
    assert f"Deleted item #{item_id}." in page
    assert "No items yet." in page


def test_delete_htmx(user_client: TestClient) -> None:
    """With htmx: CSRF token from hx-headers, empty 200 body replaces the row."""
    item_id = create(user_client, "Teapot")
    r = user_client.post(
        f"/ui/items/{item_id}/delete", headers={"HX-Request": "true"}, follow_redirects=False
    )
    assert r.status_code == 200
    assert r.text == ""
    assert user_client.get(f"/api/items/{item_id}").status_code == 404


def test_delete_needs_csrf(logged_in_client: TestClient) -> None:
    csrf = csrf_token_from(logged_in_client.get("/ui/items").text)
    item_id = create_with_token(logged_in_client, csrf, "Teapot")
    assert logged_in_client.post(f"/ui/items/{item_id}/delete").status_code == 403
    assert logged_in_client.get(f"/api/items/{item_id}").status_code == 200


def test_delete_get_not_allowed(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    assert user_client.get(f"/ui/items/{item_id}/delete").status_code == 405


def test_delete_missing_item(user_client: TestClient) -> None:
    assert user_client.post("/ui/items/999/delete").status_code == 404


def test_layout_has_htmx_csrf_header_and_nav(user_client: TestClient) -> None:
    page = user_client.get("/ui/items").text
    token = user_client.headers["X-CSRF-Token"]
    assert f'hx-headers=\'{{"X-CSRF-Token": "{token}"}}\'' in page
    assert "/ui/static/htmx-2.0.4.min.js" in page
    assert 'href="https://testserver/ui/items/new"' in page


def test_custom_confirm_dialog(user_client: TestClient) -> None:
    page = user_client.get("/ui/items").text
    assert '<dialog id="confirm-dialog"' in page
    assert "/ui/static/confirm-dialog.js" in page
    js = user_client.get("/ui/static/confirm-dialog.js")
    assert js.status_code == 200
    assert "htmx:confirm" in js.text


def test_delete_fades_out(user_client: TestClient) -> None:
    create(user_client, "Teapot")
    assert 'hx-swap="outerHTML swap:400ms"' in user_client.get("/ui/items").text


def test_htmx_served(client: TestClient) -> None:
    r = client.get("/ui/static/htmx-2.0.4.min.js")
    assert r.status_code == 200
    assert 'version:"2.0.4"' in r.text


def create_with_token(client: TestClient, csrf: str, name: str) -> int:
    r = client.post("/api/items", json={"name": name}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201
    item_id: int = r.json()["id"]
    return item_id
