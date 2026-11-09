"""User account logic, independent of HTTP (used by the CLI now, by the login routes later)."""

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from checkout.models import User
from checkout.security import hash_password

USERNAME_PATTERN = re.compile(r"[a-z0-9_.-]{3,50}")
# Length beats complexity rules; current NIST guidance (SP 800-63B) favours long passphrases.
MIN_PASSWORD_LENGTH = 12


class UserError(ValueError):
    """Invalid input for creating a user (bad username/password, name taken)."""


def normalize_username(username: str) -> str:
    """Usernames are stored lowercase, so "Matthias" and "matthias" are the same account."""
    return username.strip().lower()


def create_user(session: Session, username: str, password: str) -> User:
    username = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(username):
        raise UserError("username must be 3-50 characters: a-z, 0-9, '_', '.', '-'")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # the UNIQUE constraint decides, even for two concurrent sign-ups
        session.rollback()
        raise UserError(f"username {username!r} is already taken") from None
    session.refresh(user)  # load server defaults (id, is_active, created_at)
    return user


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == normalize_username(username)))


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.id)))
