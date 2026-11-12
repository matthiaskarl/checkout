"""Password hashing and user creation (no HTTP involved)."""

import pytest
from sqlalchemy.orm import Session

from checkout.security import hash_password, verify_password
from checkout.users import UserError, create_user, get_user_by_username, list_users
from tests.conftest import PASSWORD


def test_hash_is_salted_and_verifiable() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first.startswith("$argon2id$")
    assert first != second  # new random salt each time
    assert PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert verify_password(PASSWORD, second)
    assert not verify_password("wrong password!", first)


def test_create_user_stores_hash_not_password(session: Session) -> None:
    user = create_user(session, "  Alice ", PASSWORD)
    assert user.id is not None
    assert user.username == "alice"  # normalized
    assert user.is_active
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash)


def test_username_lookup_is_case_insensitive(session: Session) -> None:
    create_user(session, "alice", PASSWORD)
    found = get_user_by_username(session, "ALICE")
    assert found is not None
    assert found.username == "alice"
    assert get_user_by_username(session, "bob") is None


def test_duplicate_username_rejected(session: Session) -> None:
    create_user(session, "alice", PASSWORD)
    with pytest.raises(UserError, match="already taken"):
        create_user(session, "Alice", PASSWORD)
    assert [u.username for u in list_users(session)] == ["alice"]  # session still usable


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("al", PASSWORD, "username"),
        ("alice smith", PASSWORD, "username"),
        ("x" * 51, PASSWORD, "username"),
        ("alice", "short", "at least 12"),
    ],
)
def test_invalid_input_rejected(
    session: Session, username: str, password: str, message: str
) -> None:
    with pytest.raises(UserError, match=message):
        create_user(session, username, password)
