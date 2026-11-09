"""Admin command line: users and API keys (`checkout-admin --help` lists the commands).

Reads DATABASE_URL like the web app (from the environment or ./.env), so run it from
the project directory, or from /srv/checkout for the deployed copy.
"""

import argparse
import getpass
import sys

from checkout.apikeys import create_api_key, list_api_keys, revoke_api_key
from checkout.db import SessionLocal
from checkout.users import UserError, create_user, get_user_by_username, list_users


def read_password(from_stdin: bool) -> str:
    if from_stdin:  # for scripts: `echo "$PW" | checkout-admin create-user bob --password-stdin`
        return sys.stdin.readline().rstrip("\n")
    # getpass doesn't echo and never ends up in shell history (unlike a command line argument).
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != password:
        raise UserError("passwords do not match")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="checkout-admin", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="create a user (asks for the password)")
    create.add_argument("username")
    create.add_argument("--password-stdin", action="store_true", help="read password from stdin")

    users = commands.add_parser("list-users", help="list all users")
    # Hashes aren't passwords, but they allow offline guessing: don't show them by default.
    users.add_argument("--show-hashes", action="store_true", help="also print password hashes")

    key = commands.add_parser("create-api-key", help="create an API key (shown only once)")
    key.add_argument("username", help="the user the key acts as")
    key.add_argument("--name", required=True, help='what the key is for, e.g. "laptop script"')

    commands.add_parser("list-api-keys", help="list API keys (prefix only, never the key)")

    revoke = commands.add_parser("revoke-api-key", help="delete an API key by id")
    revoke.add_argument("key_id", type=int)

    args = parser.parse_args(argv)

    with SessionLocal() as session:
        if args.command == "create-user":
            try:
                user = create_user(session, args.username, read_password(args.password_stdin))
            except UserError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            print(f"created user {user.username!r} (id {user.id})")
        elif args.command == "create-api-key":
            owner = get_user_by_username(session, args.username)
            if owner is None:
                print(f"error: no user {args.username!r}", file=sys.stderr)
                return 1
            api_key, row = create_api_key(session, owner, args.name)
            print(f"created API key {row.id} ({row.name!r}) for {owner.username!r}:")
            print(f"\n    {api_key}\n")
            print("Copy it now: only its hash is stored, it can't be shown again.")
        elif args.command == "list-api-keys":
            for row in list_api_keys(session):
                used = f"{row.last_used_at:%Y-%m-%d %H:%M}" if row.last_used_at else "never"
                print(
                    f"{row.id:>4}  {row.prefix}…  {row.user.username:<15} "
                    f"{row.name:<25} last used: {used}"
                )
        elif args.command == "revoke-api-key":
            if not revoke_api_key(session, args.key_id):
                print(f"error: no API key with id {args.key_id}", file=sys.stderr)
                return 1
            print(f"revoked API key {args.key_id}")
        else:
            for user in list_users(session):
                state = "active" if user.is_active else "inactive"
                print(
                    f"{user.id:>4}  {user.username:<20} {state:<8} {user.created_at:%Y-%m-%d %H:%M}"
                )
                if args.show_hashes:
                    print(f"      {user.password_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
