import dicesim
import pytest
from fastapi.testclient import TestClient


def test_exact_is_default(client: TestClient) -> None:
    r = client.get("/api/dicesim", params={"goal": "AAABC"})
    assert r.status_code == 200
    data = r.json()
    assert data["goal"] == ["A", "A", "A", "B", "C"]
    assert data["method"] == "exact"
    assert data["probability"] == pytest.approx(dicesim.exact_probability(list("AAABC")))
    assert "trials" not in data  # simulation-only fields are omitted


def test_simulation(client: TestClient) -> None:
    params: dict[str, str | int] = {
        "goal": "BBBC",
        "method": "simulation",
        "trials": 5000,
        "seed": 1,
    }
    data = client.get("/api/dicesim", params=params).json()
    assert data["method"] == "simulation"
    assert data["trials"] == 5000
    assert 0 <= data["successes"] <= 5000
    exact = dicesim.exact_probability(list("BBBC"))
    assert abs(data["probability"] - exact) < 4 * data["standard_error"]
    # Same seed -> same result
    assert client.get("/api/dicesim", params=params).json() == data


@pytest.mark.parametrize(
    ("params", "loc"),
    [
        ({"goal": "AXB"}, ["query", "goal"]),  # symbol not on any face (dicesim's check)
        ({"goal": ""}, ["query", "goal"]),  # too short
        ({"goal": "AAAAAA"}, ["query", "goal"]),  # more symbols than dice
        ({"goal": "A", "method": "magic"}, ["query", "method"]),
        ({"goal": "A", "method": "simulation", "trials": 10**6}, ["query", "trials"]),
        ({}, ["query", "goal"]),  # missing
    ],
)
def test_invalid_input_is_422(
    client: TestClient, params: dict[str, str | int], loc: list[str]
) -> None:
    r = client.get("/api/dicesim", params=params)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == loc


def test_unknown_symbol_message(client: TestClient) -> None:
    detail = client.get("/api/dicesim", params={"goal": "AXB"}).json()["detail"][0]
    assert detail["msg"] == "symbols not on any face: X"


def test_listed_in_openapi(client: TestClient) -> None:
    assert "/api/dicesim" in client.get("/api/openapi.json").json()["paths"]
