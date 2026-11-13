"""The htmx dice section on the list page (/ui/dice fragment + no-JS fallback)."""

import pytest
from fastapi.testclient import TestClient


def test_section_on_list_page(user_client: TestClient) -> None:
    page = user_client.get("/ui/items").text
    assert '<details class="dice">' in page  # closed until something was calculated
    assert page.count('<select name="symbol"') == 5
    assert 'hx-get="https://testserver/ui/dice"' in page
    assert 'hx-target="#dice-result"' in page


def test_fragment_only(user_client: TestClient) -> None:
    """What htmx gets: just the result, no layout around it."""
    r = user_client.get("/ui/dice?symbol=A&symbol=A&symbol=A&symbol=B&symbol=C")
    assert r.status_code == 200
    assert "<html" not in r.text
    assert "<strong>A A A B C</strong>" in r.text
    assert "55.97 %" in r.text


def test_empty_selects_are_ignored(user_client: TestClient) -> None:
    r = user_client.get("/ui/dice?symbol=C&symbol=&symbol=B&symbol=&symbol=")
    assert "<strong>B C</strong>" in r.text  # sorted, blanks dropped


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("symbol=&symbol=", "Choose at least one symbol."),
        ("", "Choose at least one symbol."),
        ("symbol=X", "symbols not on any face: X"),
    ],
)
def test_fragment_errors(user_client: TestClient, query: str, message: str) -> None:
    r = user_client.get(f"/ui/dice?{query}")
    assert r.status_code == 200  # htmx only swaps 2xx responses by default
    assert f'<p class="error">{message}</p>' in r.text


def test_no_js_fallback_renders_full_page(user_client: TestClient) -> None:
    """Without htmx the form GETs the list page, which shows the result in place."""
    page = user_client.get("/ui/items?symbol=B&symbol=B&symbol=B&symbol=C&symbol=").text
    assert '<details class="dice" open>' in page
    assert "<strong>B B B C</strong>" in page
    assert page.count('<option value="B" selected>') == 3  # choices kept
    assert page.count('<option value="" selected>') == 1


def test_requires_login(client: TestClient) -> None:
    r = client.get("/ui/dice?symbol=A", follow_redirects=False)
    assert r.status_code == 303
    assert "/ui/login" in r.headers["location"]
