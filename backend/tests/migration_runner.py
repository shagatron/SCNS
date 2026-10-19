"""Destructive migration rehearsal restricted to a dedicated *_migration_test database."""

import os
import secrets
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


def main():
    url = os.environ.get(
        "MIGRATION_DATABASE_URL",
        "postgresql+psycopg://scns:scns_local@localhost:54329/scns_migration_test",
    )
    database = make_url(url).database
    if not database or not database.endswith("_migration_test"):
        raise SystemExit("Migration database name must end with _migration_test; it will be reset.")
    os.environ.update(DATABASE_URL=url, APP_ENV="test", DEMO_ENABLED="true")
    from app.cli.dataset import read_bundle, seed_bundle
    from app.models.admin import PlaceAlias
    from app.services.catalog import normalize

    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(url)
    bundle = read_bundle(Path(__file__).resolve().parents[2] / "data/demo/campus.json")
    with Session(engine) as db, db.begin():
        release = seed_bundle(db, bundle)
        revision_id = release.dataset_revision_id
        release_id = release.id
        checksum = release.checksum
    # Exercise backfill against pre-existing frozen M1 rows, not only empty tables.
    command.downgrade(config, "0003_frame_dimensions")
    command.upgrade(config, "head")
    with Session(engine) as db, db.begin():
        aliases = db.scalars(select(PlaceAlias)).all()
        expected = {(p.id, normalize(value)) for p in bundle.places for value in p.aliases}
        assert {(a.place_id, a.normalized) for a in aliases} == expected
        assert db.execute(text("SELECT release_id FROM active_releases")).scalar_one() == release_id
        assert (
            db.execute(
                text("SELECT checksum FROM dataset_revisions WHERE id=:id"), {"id": revision_id}
            ).scalar_one()
            == checksum
        )
        try:
            with db.begin_nested():
                db.execute(text("DELETE FROM place_aliases"))
        except DBAPIError:
            pass
        else:
            raise AssertionError("Frozen alias protection is missing")
    command.check(config)
    engine.dispose()
    cli = [
        sys.executable,
        "-m",
        "app.cli.admin",
        "bootstrap-admin",
        "--username",
        "rehearsal-owner",
        "--display-name",
        "Rehearsal owner",
        "--campus",
        "DEMO",
        "--password-stdin",
    ]
    password = secrets.token_urlsafe(32)
    first = subprocess.run(cli, input=password + "\n", text=True, capture_output=True, check=False)
    second = subprocess.run(cli, input=password + "\n", text=True, capture_output=True, check=False)
    assert first.returncode == 0 and second.returncode == 2
    assert "already consumed" in second.stderr
    assert password not in first.stdout + first.stderr + second.stdout + second.stderr
    print(
        "Trusted-host CLI bootstrap passed; second invocation rejected without printing credentials."
    )
    print(
        "Migration rehearsal passed: fresh schema, M1 downgrade/upgrade, alias backfill, active release/checksum preservation, frozen alias guard and model/schema alignment."
    )


if __name__ == "__main__":
    main()
