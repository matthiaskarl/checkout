"""Admin command line: `checkout-admin create-user <name>`, `checkout-admin list-users`.

Reads DATABASE_URL like the web app (from the environment or ./.env), so run it from
the project directory, or from /srv/checkout for the deployed copy.
"""

import argparse
import getpass
import sys

from checkout.db import SessionLocal
from checkout.users import UserError, create_user, list_users


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

    args = parser.parse_args(argv)

    with SessionLocal() as session:
        if args.command == "create-user":
            try:
                user = create_user(session, args.username, read_password(args.password_stdin))
            except UserError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            print(f"created user {user.username!r} (id {user.id})")
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
