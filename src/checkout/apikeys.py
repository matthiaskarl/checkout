"""API keys for programmatic access (e.g. /api/dicesim from scripts), independent of HTTP.

Compared with the "hardcoded key in a header" approach:
- one key per user and purpose, so each can be revoked alone (delete the row),
- the server stores only a SHA-256 of the key (a DB leak exposes no usable keys),
- keys carry a recognizable prefix ("ck_"), so secret scanners and humans spot leaks.
"""

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from checkout.models import ApiKey, User
from checkout.sessions import utcnow

KEY_PREFIX = "ck_"  # "checkout key"
PREFIX_LENGTH = 10  # stored/displayed: "ck_" + 7 characters of the random part


def _hash_key(key: str) -> str:
    # 256 random bits: unguessable, so a fast hash is fine (same reasoning as session tokens).
    return hashlib.sha256(key.encode()).hexdigest()


def create_api_key(db: Session, user: User, name: str) -> tuple[str, ApiKey]:
    """Return (key, row). The key is not stored anywhere: show it once, then it's gone."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    row = ApiKey(user=user, name=name, key_hash=_hash_key(key), prefix=key[:PREFIX_LENGTH])
    db.add(row)
    db.commit()
    db.refresh(row)
    return key, row


def user_for_api_key(db: Session, key: str) -> User | None:
    """The key's owner, or None if the key is unknown or the user is deactivated."""
    row = db.scalar(select(ApiKey).where(ApiKey.key_hash == _hash_key(key)))
    if row is None or not row.user.is_active:
        return None
    row.last_used_at = utcnow()
    db.commit()
    return row.user


def list_api_keys(db: Session) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).order_by(ApiKey.id)))


def revoke_api_key(db: Session, key_id: int) -> bool:
    """Delete the key; True if it existed. Takes effect on the very next request."""
    row = db.get(ApiKey, key_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
