"""Actual built helper/API/import worker, owned disposable DB; no developer writes."""

import os
import secrets
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.cli.admin import bootstrap
from app.cli.dataset import read_bundle, seed_bundle
from app.cli.indoor_demo import DemoError
from app.cli.muj import LocalClient, stage
from app.models import ActiveRelease, Campus, Edge, Place, Revision
from app.models.admin import AuditEvent
from app.models.imports import ImportJob
from app.models.publication import SourceAsset
from app.services.muj_setup import CAMPUS_ID, ROOT


def main():
    url = os.environ["DATABASE_URL"]
    database = make_url(url).database
    if (
        os.environ.get("APP_ENV") != "test"
        or not database.startswith("scns_demo_")
        or not database.endswith("_e2e_test")
    ):
        raise RuntimeError("Owned disposable database required")
    engine = create_engine(url)
    password = secrets.token_urlsafe(32)
    bundle = read_bundle(Path("/app/data/demo/campus.json"))
    with Session(engine) as db, db.begin():
        release = seed_bundle(db, bundle)
        bootstrap(db, "muj-test-owner", "Ephemeral owner", password, bundle.campus.id)
        before = str(release.id)
    client = LocalClient()
    client.login("muj-test-owner", password)
    try:
        # Stop deliberately after the worker prepares the first preview; rerun reconciles it.
        try:
            stage(client, ROOT, confirm=lambda _: "STOP")
        except DemoError as exc:
            assert "Stopped before apply" in str(exc)
        else:
            raise AssertionError("Expected bounded interruption")
        state = stage(client, ROOT, confirm=lambda _: "APPLY")
        with Session(engine) as db:
            revision = db.get(Revision, UUID(state["draft_id"]))
            v = revision.edit_version
            counts = {
                m.__tablename__: db.scalar(
                    select(func.count()).select_from(m).where(m.campus_id == CAMPUS_ID)
                )
                for m in (Campus, Revision, Edge, Place, ImportJob)
            }
            assert revision.status == "draft"
            assert db.get(ActiveRelease, (CAMPUS_ID, "public")) is None
            assert str(db.get(ActiveRelease, (bundle.campus.id, "public")).release_id) == before
            assert all(
                s.approved_by is None
                for s in db.scalars(select(SourceAsset).where(SourceAsset.campus_id == CAMPUS_ID))
            )
            assert (
                counts["import_jobs"] == 3
                and counts["navigation_edges"] == 638
                and counts["places"] == 55
            )
            audits = db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.campus_id == CAMPUS_ID)
            )
        repeated = stage(
            client,
            ROOT,
            confirm=lambda _: (_ for _ in ()).throw(
                AssertionError("Committed replay must not prompt")
            ),
        )
        assert repeated["draft_id"] == state["draft_id"]
        with Session(engine) as db:
            assert db.get(Revision, UUID(state["draft_id"])).edit_version == v
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.campus_id == CAMPUS_ID)
                )
                == audits
            )
        print(
            "PASS built MUJ helper: interrupted preview resumed; three real-worker batches applied; replay unchanged; draft/source/audit/public isolation; route evidence prepared."
        )
    finally:
        client.logout()
        engine.dispose()


if __name__ == "__main__":
    main()
