"""Login and server-side sessions, independent of HTTP (cookies are handled in checkout.auth)."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from checkout.models import LoginSession, User
from checkout.security import hash_password, verify_password
from checkout.users import get_user_by_username

SESSION_LIFETIME = timedelta(days=7)

# Checked against when the username doesn't exist, so that case takes as long as a wrong
# password. Otherwise response times would reveal which usernames exist.
_DUMMY_HASH = hash_password("no such user - timing equalizer")


def utcnow() -> datetime:
    """Naive UTC 'now' (DATETIME columns in MySQL carry no time zone)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    # A plain SHA-256 is enough here (unlike passwords): the token is 256 random bits,
    # so there is nothing to guess, and lookups must be fast.
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(db: Session, username: str, password: str) -> User | None:
    """Return the user if the credentials are valid and the account is active."""
    user = get_user_by_username(db, username)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def start_session(db: Session, user: User) -> str:
    """Create a session row and return the token for the cookie (never stored as-is)."""
    token = secrets.token_urlsafe(32)  # 32 random bytes from the OS
    db.add(LoginSession(id=_hash_token(token), user=user, expires_at=utcnow() + SESSION_LIFETIME))
    db.commit()
    return token


def user_for_token(db: Session, token: str) -> User | None:
    """The logged-in user for a cookie token, or None if unknown, expired or deactivated."""
    login = db.get(LoginSession, _hash_token(token))
    if login is None or login.expires_at <= utcnow() or not login.user.is_active:
        return None
    return login.user


def end_session(db: Session, token: str) -> None:
    db.execute(delete(LoginSession).where(LoginSession.id == _hash_token(token)))
    db.commit()
