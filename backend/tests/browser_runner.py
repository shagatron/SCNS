"""Run browsers against an explicitly disposable database, never the developer dataset."""

import os
import secrets
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    root = Path(__file__).resolve().parents[2]
    url = os.environ.get(
        "E2E_DATABASE_URL", "postgresql+psycopg://scns:scns_local@localhost:54329/scns_e2e_test"
    )
    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_e2e_test"):
        raise SystemExit("Browser database name must end with _e2e_test; it will be reset.")
    os.environ.update(
        DATABASE_URL=url,
        APP_ENV="test",
        DEMO_ENABLED="true",
        ALLOWED_ORIGINS='["http://127.0.0.1:5174"]',
        API_PROXY_TARGET="http://127.0.0.1:8001",
        SESSION_COOKIE_SECURE="false",
    )
    # Application imports must follow the test environment configuration.
    from app.cli.admin import bootstrap
    from app.cli.dataset import read_bundle, seed_bundle
    from app.models.admin import RoleAssignment, User
    from app.services.admin_auth import HASHER

    config = Config(str(root / "backend/alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    password = secrets.token_urlsafe(32)
    engine = create_engine(url)
    with Session(engine) as db, db.begin():
        bundle = read_bundle(root / "data/demo/campus.json")
        seed_bundle(db, bundle)
        bootstrap(db, "browser-owner", "Browser owner", password, bundle.campus.id)
        for role in ["editor", "reviewer_publisher", "operations"]:
            user = User(
                username=f"browser-{role}", display_name=role, password_hash=HASHER.hash(password)
            )
            db.add(user)
            db.flush()
            db.add(RoleAssignment(user_id=user.id, campus_id=bundle.campus.id, role=role))
    engine.dispose()
    # Ephemeral credentials only in child environment, never argv, files, traces or output.
    env = {**os.environ, "SCNS_E2E_PASSWORD": password}
    with tempfile.TemporaryDirectory(prefix="scns-import-browser-") as storage:
        env["STORAGE_ROOT"] = storage
        worker = subprocess.Popen(
            [sys.executable, "-m", "app.cli.imports", "worker"],
            cwd=root / "backend",
            env=env,
            start_new_session=True,
        )
        try:
            result = subprocess.run(
                ["npm", "run", "test:e2e", "--", *sys.argv[1:]],
                cwd=root / "frontend",
                env=env,
                check=False,
            )
        finally:
            os.killpg(worker.pid, signal.SIGTERM)
            worker.wait(timeout=10)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
