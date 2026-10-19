"""Trusted-host identity provisioning. Passwords are never command-line arguments."""

import argparse
import getpass
import sys
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import Campus
from app.models.admin import BootstrapState, RoleAssignment, User
from app.schemas.admin import UserInput
from app.services.admin_auth import HASHER, PERMISSIONS, audit


def bootstrap(db: Session, username: str, display_name: str, password: str, campus_id):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('scns-admin-bootstrap'))"))
    if db.get(BootstrapState, 1) or db.scalar(select(User.id).limit(1)):
        raise ValueError(
            "Bootstrap is already consumed. Use an authorized administrator or trusted-host grant-role command."
        )
    if db.get(Campus, campus_id) is None:
        raise ValueError("Campus does not exist; migrate and seed the explicit demo first.")
    data = UserInput(
        username=username, display_name=display_name, password=password, role="system_admin"
    )
    user = User(
        id=uuid4(),
        username=data.username,
        display_name=data.display_name,
        password_hash=HASHER.hash(data.password.get_secret_value()),
    )
    db.add(user)
    db.flush()
    db.add(RoleAssignment(user_id=user.id, campus_id=campus_id, role="system_admin"))
    db.add(BootstrapState(id=1, user_id=user.id))
    audit(
        db,
        "identity.bootstrap",
        "trusted-host-cli",
        actor_id=user.id,
        campus_id=campus_id,
        resource_id=user.id,
        after={"username": user.username, "role": "system_admin"},
    )
    return user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap-admin", "grant-role"])
    parser.add_argument("--username", required=True)
    parser.add_argument("--campus", required=True, help="Existing campus code")
    parser.add_argument("--display-name")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read one password line from a secure pipe instead of prompting",
    )
    parser.add_argument("--role", choices=sorted(PERMISSIONS))
    args = parser.parse_args()
    try:
        with Session(engine.execution_options(isolation_level="READ COMMITTED")) as db, db.begin():
            campus = db.scalar(select(Campus).where(Campus.code == args.campus))
            if not campus:
                raise ValueError("Unknown campus code")
            if args.command == "bootstrap-admin":
                if not args.display_name:
                    raise ValueError("--display-name is required")
                # Check before prompting, then recheck under the lock in bootstrap().
                if db.get(BootstrapState, 1):
                    raise ValueError("Bootstrap is already consumed")
                password = (
                    sys.stdin.readline(130).rstrip("\r\n")
                    if args.password_stdin
                    else getpass.getpass("New admin password (12–128 characters): ")
                )
                if not args.password_stdin and password != getpass.getpass("Confirm password: "):
                    raise ValueError("Passwords do not match")
                user = bootstrap(db, args.username, args.display_name, password, campus.id)
                print(
                    f"Admin created for {campus.code}: {user.username}. No session or password printed."
                )
            else:
                if not args.role:
                    raise ValueError("--role is required")
                user = db.scalar(select(User).where(User.username == args.username.lower()))
                if not user:
                    raise ValueError("Unknown existing user")
                if not db.get(RoleAssignment, (user.id, campus.id, args.role)):
                    db.add(RoleAssignment(user_id=user.id, campus_id=campus.id, role=args.role))
                    audit(
                        db,
                        "identity.host_grant",
                        "trusted-host-cli",
                        campus_id=campus.id,
                        resource_id=user.id,
                        after={"role": args.role},
                    )
                print(f"Role provisioned for {user.username} in {campus.code}.")
    except ValidationError:
        parser.exit(2, "Invalid username, display name or password length (12–128 required).\n")
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
