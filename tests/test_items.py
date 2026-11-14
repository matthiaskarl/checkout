from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_item_crud(user_client: TestClient) -> None:
    r = user_client.post("/api/items", json={"name": "Widget", "description": "A thing"})
    assert r.status_code == 201
    item = r.json()
    assert item["name"] == "Widget"

    assert user_client.get(f"/api/items/{item['id']}").json()["name"] == "Widget"
    assert len(user_client.get("/api/items").json()) == 1

    r = user_client.patch(f"/api/items/{item['id']}", json={"name": "Gadget"})
    assert r.json()["name"] == "Gadget"
    assert r.json()["description"] == "A thing"

    assert user_client.delete(f"/api/items/{item['id']}").status_code == 204
    assert user_client.get(f"/api/items/{item['id']}").status_code == 404


def test_validation(user_client: TestClient) -> None:
    assert user_client.post("/api/items", json={"name": ""}).status_code == 422


def test_url_layout(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200
    assert "/api/items" in client.get("/api/openapi.json").json()["paths"]
    # Nothing outside /api or /ui
    assert client.get("/items").status_code == 404
    assert client.get("/health").status_code == 404
    assert client.get("/docs").status_code == 404


def test_patch_rejects_null_name(user_client: TestClient) -> None:
    """Regression: {"name": null} used to reach the DB (NOT NULL) and end in a 500."""
    item = user_client.post("/api/items", json={"name": "Teapot", "description": "x"}).json()
    r = user_client.patch(f"/api/items/{item['id']}", json={"name": None})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "name"]

    # Still allowed: leaving name out, and clearing the description explicitly.
    r = user_client.patch(f"/api/items/{item['id']}", json={"description": None})
    assert r.status_code == 200
    assert r.json() == {**item, "description": None}
