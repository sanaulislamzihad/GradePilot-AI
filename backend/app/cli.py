"""Command-line administration.

Usage:
    python -m app.cli create-admin --email admin@example.edu --name "System Admin"

The password is read interactively (or from GRADEPILOT_ADMIN_PASSWORD for
automated setups) so it never appears in shell history.
"""

import argparse
import getpass
import os
import sys

from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.user import User, UserRole
from app.schemas.user import validate_password_strength
from app.security.passwords import hash_password
from app.services import audit


def _read_password() -> str:
    password = os.environ.get("GRADEPILOT_ADMIN_PASSWORD")
    if password:
        return password
    password = getpass.getpass("Admin password: ")
    if password != getpass.getpass("Confirm password: "):
        sys.exit("Passwords do not match.")
    return password


def create_admin(email: str, name: str) -> None:
    try:
        email = TypeAdapter(EmailStr).validate_python(email.strip().lower())
    except ValidationError:
        sys.exit("Invalid email address.")
    if len(name.strip()) < 2:
        sys.exit("Name must be at least 2 characters.")

    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            sys.exit(f"A user with email {email} already exists.")
        try:
            password = validate_password_strength(_read_password())
        except ValueError as exc:
            sys.exit(str(exc))

        admin = User(email=email, full_name=name.strip(), password_hash=hash_password(password), role=UserRole.ADMIN)
        db.add(admin)
        db.flush()
        audit.record(db, "auth.register", actor=admin, entity_type="user", entity_id=admin.id,
                     details={"role": "admin", "source": "cli"})
        db.commit()
        print(f"Admin account created for {email}.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Create an administrator account")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    args = parser.parse_args()

    if args.command == "create-admin":
        create_admin(args.email, args.name)


if __name__ == "__main__":
    main()
