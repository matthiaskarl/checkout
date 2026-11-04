from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_item_crud(client: TestClient) -> None:
    r = client.post("/items", json={"name": "Widget", "description": "A thing"})
    assert r.status_code == 201
    item = r.json()
    assert item["name"] == "Widget"

    assert client.get(f"/items/{item['id']}").json()["name"] == "Widget"
    assert len(client.get("/items").json()) == 1

    r = client.patch(f"/items/{item['id']}", json={"name": "Gadget"})
    assert r.json()["name"] == "Gadget"
    assert r.json()["description"] == "A thing"

    assert client.delete(f"/items/{item['id']}").status_code == 204
    assert client.get(f"/items/{item['id']}").status_code == 404


def test_validation(client: TestClient) -> None:
    assert client.post("/items", json={"name": ""}).status_code == 422
