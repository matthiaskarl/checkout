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

    user: Mapped[User] = relationship(lazy="joined")  # loaded with the session in one query


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(255))
