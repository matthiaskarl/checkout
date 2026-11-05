from fastapi.testclient import TestClient


def test_form_renders(client: TestClient) -> None:
    r = client.get("/ui/items/new")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert '<form method="post"' in r.text
    assert "No items yet." in r.text


def test_create_redirects_and_shows_item(client: TestClient) -> None:
    r = client.post(
        "/ui/items/new",
        data={"name": "Teapot", "description": "short and stout"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/ui/items/new?created=" in r.headers["location"]

    page = client.get(r.headers["location"])
    assert "Created item #1" in page.text
    assert "short and stout" in page.text
    assert client.get("/api/items/1").json()["name"] == "Teapot"


def test_invalid_input_rerenders_with_error(client: TestClient) -> None:
    r = client.post("/ui/items/new", data={"name": "   ", "description": "kept"})
    assert r.status_code == 422
    assert 'class="error"' in r.text
    assert "kept" in r.text  # user's input is preserved
    assert client.get("/api/items").json() == []


def test_html_is_escaped(client: TestClient) -> None:
    client.post("/ui/items/new", data={"name": "<script>alert(1)</script>"})
    page = client.get("/ui/items/new")
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text
