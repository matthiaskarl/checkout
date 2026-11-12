"""ORM models (database tables)."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from checkout.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    # Never the password itself: an argon2 hash string like "$argon2id$v=19$m=...$<salt>$<hash>".
    password_hash: Mapped[str] = mapped_column(String(255))
    # Lets you lock an account without deleting it (and its history).
    is_active: Mapped[bool] = mapped_column(server_default=true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LoginSession(Base):
    """One row per logged-in browser. The cookie holds a random token; we store only its hash."""

    __tablename__ = "login_sessions"

    # SHA-256 hex of the cookie token: a leaked DB dump contains no usable cookies.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # ondelete=CASCADE: deleting a user deletes their sessions in the same step.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]  # naive UTC, set by checkout.sessions
    # Secret per session, embedded in our own pages/requests. A foreign page can make the
    # browser send the cookie, but it can't read our pages, so it can't know this value.
    csrf_token: Mapped[str] = mapped_column(String(64))

    user: Mapped[User] = relationship(lazy="joined")  # loaded with the session in one query


class ApiKey(Base):
    """A long-lived key for programmatic API access, sent as `Authorization: Bearer <key>`.

    Like sessions, only a SHA-256 of the key is stored; the key itself is shown once at
    creation. Revoking = deleting the row.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))  # what it's for, e.g. "laptop script"
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # First characters of the key, to recognize it in lists and logs without revealing it.
    prefix: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime | None]  # naive UTC; shows which keys are still in use

    user: Mapped[User] = relationship(lazy="joined")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255))
