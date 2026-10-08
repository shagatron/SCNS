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
        # More authenticated journeys share one test-proxy IP; production default remains 30.
        LOGIN_IP_LIMIT="100",
    )
    # Application imports must follow the test environment configuration.
    from app.cli.admin import bootstrap
    from app.cli.dataset import read_bundle, seed_bundle
    from app.models.admin import RoleAssignment, User
    from app.services.admin_auth import HASHER
    from tests.publication_fixtures import create_fixture

    config = Config(str(root / "backend/alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    password = secrets.token_urlsafe(32)
    engine = create_engine(url)
    with Session(engine) as db, db.begin():
        bundle = read_bundle(root / "data/demo/campus.json")
        release = seed_bundle(db, bundle)
        fixture_campuses = [
            create_fixture(db, release.dataset_revision_id, bundle, viewport)
            for viewport in ("desktop", "mobile")
        ]
        fixture_campuses.extend(
            create_fixture(db, release.dataset_revision_id, bundle, viewport, purpose)
            for purpose in (
                "floorplan",
                "floorplan conflicts",
                "indoor",
                "indoor conflicts",
                "indoor routing",
                "indoor routing conflicts",
            )
            for viewport in ("desktop", "mobile")
        )
        owner = bootstrap(db, "browser-owner", "Browser owner", password, bundle.campus.id)
        for campus_id in fixture_campuses:
            db.add(RoleAssignment(user_id=owner.id, campus_id=campus_id, role="system_admin"))
        for role in ["editor", "reviewer_publisher", "operations"]:
            user = User(
                username=f"browser-{role}", display_name=role, password_hash=HASHER.hash(password)
            )
            db.add(user)
            db.flush()
            for campus_id in [bundle.campus.id, *fixture_campuses]:
                db.add(RoleAssignment(user_id=user.id, campus_id=campus_id, role=role))
    engine.dispose()
    # Ephemeral credentials only in child environment, never argv, files, traces or output.
    env = {**os.environ, "SCNS_E2E_PASSWORD": password}
    with tempfile.TemporaryDirectory(prefix="scns-import-browser-") as storage:
        env["STORAGE_ROOT"] = storage
        worker_name = env.get("SCNS_E2E_BUILT_WORKER_CONTAINER")
        worker = None
        if worker_name:
            if not worker_name.startswith("scns-publication-smoke-") or not worker_name.endswith(
                "-worker"
            ):
                raise RuntimeError("Built worker must be an owned smoke container")
            subprocess.run(["docker", "start", worker_name], stdout=subprocess.DEVNULL, check=True)
        else:
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
            if worker:
                os.killpg(worker.pid, signal.SIGTERM)
                worker.wait(timeout=10)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
