"""Password hashing with argon2id (via pwdlib).

A hash string carries everything needed to check it later, e.g.

    $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
     algorithm  ver  cost settings  random  result

so no separate salt column is needed, and the cost settings can be raised later
without breaking existing hashes.
"""

from pwdlib import PasswordHash

# argon2id with pwdlib's current recommended cost settings.
_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return a new hash. Hashing the same password twice gives different strings (new salt)."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Re-hash `password` with the salt and settings stored in `password_hash` and compare."""
    return _hasher.verify(password, password_hash)
