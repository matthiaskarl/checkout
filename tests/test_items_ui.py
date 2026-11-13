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


# --- edit -------------------------------------------------------------------------------------


def test_edit_form_prefilled(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    page = user_client.get(f"/ui/items/{item_id}/edit").text
    assert f"<h1>Edit item #{item_id}</h1>" in page
    assert 'value="Teapot"' in page
    assert ">about Teapot</textarea>" in page
    assert f'action="https://testserver/ui/items/{item_id}/edit"' in page
    assert ">Save</button>" in page


def test_list_links_to_edit(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    assert f'href="https://testserver/ui/items/{item_id}/edit"' in user_client.get("/ui/items").text


def test_edit_saves_and_redirects(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    r = user_client.post(
        f"/ui/items/{item_id}/edit",
        data={"name": " Kettle ", "description": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith(f"/ui/items?updated={item_id}")
    page = user_client.get(r.headers["location"]).text
    assert f"Saved item #{item_id}: <strong>Kettle</strong>" in page
    assert f'<tr id="item-{item_id}" class="new">' in page

    item = user_client.get(f"/api/items/{item_id}").json()
    assert item["name"] == "Kettle"  # stripped
    assert item["description"] is None  # empty field clears it: full update


def test_edit_invalid_keeps_input_and_item(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    r = user_client.post(f"/ui/items/{item_id}/edit", data={"name": "  ", "description": "new"})
    assert r.status_code == 422
    assert 'class="error"' in r.text
    assert ">new</textarea>" in r.text  # what the user typed, not the stored value
    assert f"<h1>Edit item #{item_id}</h1>" in r.text  # still the edit form
    assert user_client.get(f"/api/items/{item_id}").json()["name"] == "Teapot"


def test_edit_missing_item(user_client: TestClient) -> None:
    assert user_client.get("/ui/items/999/edit").status_code == 404
    assert user_client.post("/ui/items/999/edit", data={"name": "x"}).status_code == 404


def test_edit_needs_csrf(logged_in_client: TestClient) -> None:
    csrf = csrf_token_from(logged_in_client.get("/ui/items").text)
    item_id = create_with_token(logged_in_client, csrf, "Teapot")
    r = logged_in_client.post(f"/ui/items/{item_id}/edit", data={"name": "Hacked"})
    assert r.status_code == 403


# --- inline editing (htmx row fragments) ------------------------------------------------------


def test_edit_link_is_inline_with_page_fallback(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    page = user_client.get("/ui/items").text
    assert f'href="https://testserver/ui/items/{item_id}/edit"' in page  # without JS
    assert f'hx-get="https://testserver/ui/items/{item_id}/row/edit"' in page  # with htmx
    assert 'hx-trigger="click[!ctrlKey &amp;&amp; !metaKey &amp;&amp; !shiftKey]"' not in page
    assert 'hx-trigger="click[!ctrlKey && !metaKey && !shiftKey]"' in page  # modifier clicks


def test_edit_row_fragment(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    r = user_client.get(f"/ui/items/{item_id}/row/edit")
    assert r.status_code == 200
    assert r.text.strip().startswith(f'<tr id="item-{item_id}" class="editing"')
    assert "<html" not in r.text
    assert f'form="edit-item-{item_id}" name="name" value="Teapot"' in r.text
    assert f'hx-put="https://testserver/ui/items/{item_id}/row"' in r.text


def test_cancel_returns_display_row(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    r = user_client.get(f"/ui/items/{item_id}/row")
    assert r.text.strip().startswith(f'<tr id="item-{item_id}">')
    assert "<td>Teapot</td>" in r.text


def test_inline_save(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    r = user_client.put(f"/ui/items/{item_id}/row", data={"name": " Kettle ", "description": "hot"})
    assert r.status_code == 200
    assert r.text.strip().startswith(f'<tr id="item-{item_id}" class="new">')
    assert "<td>Kettle</td>" in r.text
    assert user_client.get(f"/api/items/{item_id}").json()["description"] == "hot"


def test_inline_invalid_returns_edit_row_with_422(user_client: TestClient) -> None:
    item_id = create(user_client, "Teapot")
    r = user_client.put(f"/ui/items/{item_id}/row", data={"name": " ", "description": "x"})
    assert r.status_code == 422
    assert 'class="editing"' in r.text
    assert '<p class="error">' in r.text
    assert 'name="description" value="x"' in r.text  # what was typed is kept
    assert user_client.get(f"/api/items/{item_id}").json()["name"] == "Teapot"


def test_inline_save_needs_csrf(logged_in_client: TestClient) -> None:
    csrf = csrf_token_from(logged_in_client.get("/ui/items").text)
    item_id = create_with_token(logged_in_client, csrf, "Teapot")
    r = logged_in_client.put(f"/ui/items/{item_id}/row", data={"name": "Hacked"})
    assert r.status_code == 403


def test_inline_missing_item(user_client: TestClient) -> None:
    assert user_client.get("/ui/items/999/row/edit").status_code == 404
    assert user_client.put("/ui/items/999/row", data={"name": "x"}).status_code == 404


def test_htmx_config_swaps_422(user_client: TestClient) -> None:
    page = user_client.get("/ui/items").text
    assert '<meta name="htmx-config"' in page
    assert '{"code": "422", "swap": true}' in page
