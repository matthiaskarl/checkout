"""API keys (Authorization: Bearer) for the public /api/dicesim endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from checkout.apikeys import create_api_key, list_api_keys, revoke_api_key
from checkout.cli import main as cli
from checkout.models import ApiKey, User

DICE = "/api/dicesim?goal=AB"


def test_key_format_and_storage(session: Session, user: User) -> None:
    key, row = create_api_key(session, user, "laptop")
    assert key.startswith("ck_")
    assert len(key) > 40
    assert row.prefix == key[:10]
    assert row.key_hash != key
    assert key not in row.key_hash  # only the SHA-256 is stored


def test_anonymous_gets_401_with_challenge(client: TestClient) -> None:
    r = client.get(DICE)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json() == {"detail": "API key or login required"}


def test_valid_key(key_client: TestClient, session: Session) -> None:
    assert key_client.get(DICE).status_code == 200
    assert list_api_keys(session)[0].last_used_at is not None


@pytest.mark.parametrize("header", ["Bearer ck_wrong", "Bearer ", "Basic YWxpY2U6eA=="])
def test_invalid_key(client: TestClient, user: User, header: str) -> None:
    r = client.get(DICE, headers={"Authorization": header})
    assert r.status_code == 401


def test_bad_key_does_not_fall_back_to_session(user_client: TestClient) -> None:
    r = user_client.get(DICE, headers={"Authorization": "Bearer ck_wrong"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid API key"}


def test_session_works_without_key(user_client: TestClient) -> None:
    """Our own pages (React/Jinja) can call dicesim with the login cookie."""
    assert user_client.get(DICE).status_code == 200


def test_key_only_opens_dicesim(key_client: TestClient) -> None:
    """A key is not a login: the first-party routes stay cookie-only."""
    assert key_client.get("/api/items").status_code == 401
    assert key_client.get("/api/session").status_code == 401


def test_revoked_key(key_client: TestClient, session: Session) -> None:
    assert revoke_api_key(session, list_api_keys(session)[0].id)
    assert key_client.get(DICE).status_code == 401
    assert not revoke_api_key(session, 999)


def test_deactivated_user_key(key_client: TestClient, session: Session, user: User) -> None:
    user.is_active = False
    session.commit()
    assert key_client.get(DICE).status_code == 401


def test_deleting_user_deletes_keys(session: Session, user: User) -> None:
    create_api_key(session, user, "x")
    session.delete(user)
    session.commit()
    assert session.query(ApiKey).count() == 0


def test_listed_in_openapi(client: TestClient) -> None:
    schemes = client.get("/api/openapi.json").json()["components"]["securitySchemes"]
    assert schemes["API key"] == {
        "type": "http",
        "scheme": "bearer",
        "description": "An API key from `checkout-admin create-api-key` (starts with ck_).",
    }


def test_cli_create_list_revoke(
    session: Session,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Point the CLI at the test database instead of the real one.
    from sqlalchemy.orm import sessionmaker

    import checkout.cli

    bind = session.get_bind()
    monkeypatch.setattr(
        checkout.cli, "SessionLocal", sessionmaker(bind=bind, expire_on_commit=False)
    )

    assert cli(["create-api-key", "alice", "--name", "cli test"]) == 0
    out = capsys.readouterr().out
    key = next(line.strip() for line in out.splitlines() if line.strip().startswith("ck_"))

    assert cli(["list-api-keys"]) == 0
    listing = capsys.readouterr().out
    assert key[:10] in listing
    assert key not in listing  # never the full key

    assert cli(["revoke-api-key", "1"]) == 0
    assert cli(["create-api-key", "nobody", "--name", "x"]) == 1
