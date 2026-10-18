"""Real logical restore/reconciliation on owned DBs; not Windows/DPAPI proof on Linux."""

import copy
import importlib.util
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.cli.admin import bootstrap
from app.cli.dataset import read_bundle, seed_bundle
from app.core.config import get_settings
from app.services.admin_catalog import create_draft

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "native_migration_tool", ROOT / "scripts/windows/native.py"
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("interruption", ["after-success", "partial-storage"])
def test_actual_restore_recovery_and_no_original_writes(tmp_path, monkeypatch, interruption):
    url = make_url(os.environ["TEST_DATABASE_URL"])
    if not url.database.endswith("_test"):
        pytest.fail("Disposable test database URL required")
    admin = {
        "host": url.host,
        "port": url.port,
        "user": url.username,
        "password": url.password,
        "dbname": "postgres",
    }
    source = "scns_native_source_" + uuid4().hex[:10] + "_test"
    prefix = "scns_native_"
    created_roles = []
    created_databases = [source]
    source_url = url.set(database=source)
    state = tmp_path / "state"
    state.mkdir()
    bundle = tmp_path / "backup"
    files = bundle / "files"
    (files / "storage").mkdir(parents=True)
    (files / "storage/private").mkdir()
    (files / "storage/private/receipt.json").write_text('{"synthetic":"existing-journal"}')
    (files / "repository/storage/private").mkdir(parents=True)
    (files / "repository/storage/private/helper.json").write_text(
        '{"synthetic":"existing-helper-receipt"}'
    )
    real_run = native.run
    if os.name == "nt":
        folder = native.tools()
    else:
        folder = Path("/isolated-test-tools")
    restores = []

    def runner(args, **kwargs):
        if Path(str(args[0])).name in {"pg_restore", "pg_restore.exe"}:
            restores.append(1)
            if os.name == "nt":
                return real_run(args, **kwargs)
            container = subprocess.check_output(
                ["docker", "compose", "ps", "-q", "db"], cwd=ROOT, text=True
            ).strip()
            with Path(args[-1]).open("rb") as source_file:
                p = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        "-e",
                        "PGUSER",
                        "-e",
                        "PGPASSWORD",
                        "-e",
                        "PGDATABASE",
                        container,
                        "pg_restore",
                        *args[1:-1],
                    ],
                    stdin=source_file,
                    capture_output=True,
                    env=kwargs["env"],
                )
            if p.returncode:
                import re

                lines = p.stderr.decode(errors="replace").splitlines()
                category = "; ".join(re.sub(r"'[^']*'", "'<redacted>'", line) for line in lines[:3])
                raise native.SafeError(
                    f"Disposable pg_restore failed: {category}; no credential output"
                )
            return p.stdout
        return real_run(args, **kwargs)

    monkeypatch.setattr(native, "run", runner)
    monkeypatch.setattr(native, "protect", lambda p: p.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(native, "admin_connection", lambda: admin.copy())
    secret_store = {}

    def fake_save(path, value):
        # Synthetic credentials remain in memory; never fake DPAPI with plaintext.
        secret_store[path] = copy.deepcopy(value)
        native.write(path, {"synthetic_mock_dpapi": True})

    def fake_load(path):
        return copy.deepcopy(secret_store[path]) if path in secret_store else native.read(path)

    monkeypatch.setattr(native, "save_secret", fake_save)
    monkeypatch.setattr(native, "load_secret", fake_load)
    monkeypatch.setattr("builtins.input", lambda _: "RESTORE SCNS")
    try:
        with psycopg.connect(**admin, autocommit=True) as db:
            db.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(source))
            )
        monkeypatch.setenv("DATABASE_URL", source_url.render_as_string(hide_password=False))
        monkeypatch.setenv("DEMO_ENABLED", "true")
        get_settings.cache_clear()
        command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
        engine = create_engine(source_url)
        with Session(engine) as db, db.begin():
            demo = read_bundle(ROOT / "data/demo/campus.json")
            seed_bundle(db, demo)
            actor = bootstrap(
                db,
                "copy-test-owner",
                "Synthetic restore test owner",
                (actor_password := uuid4().hex + "!Only"),
                demo.campus.id,
            )
            create_draft(db, demo.campus.id, actor.id, "synthetic-copy-migration", "copy-test")
        engine.dispose()
        with psycopg.connect(**{**admin, "dbname": source}) as db:
            snapshot = native.inventory(db)
        dump = files / "database.dump"
        if os.name == "nt":
            with dump.open("wb") as f:
                real_run(
                    [native.pg(folder, "pg_dump"), "-Fc", "--no-owner", "--no-acl"],
                    stdout=f,
                    env={
                        **os.environ,
                        "PGHOST": admin["host"],
                        "PGPORT": str(admin["port"]),
                        "PGUSER": admin["user"],
                        "PGPASSWORD": admin["password"],
                        "PGDATABASE": source,
                    },
                )
        else:
            with dump.open("wb") as f:
                p = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "-T",
                        "db",
                        "pg_dump",
                        "-U",
                        admin["user"],
                        "-d",
                        source,
                        "-Fc",
                        "--no-owner",
                        "--no-acl",
                    ],
                    cwd=ROOT,
                    stdout=f,
                    stderr=subprocess.PIPE,
                )
                assert p.returncode == 0
        report = {
            "format": "scns-native-backup-v1",
            "complete": True,
            "source": snapshot,
            "files": native.file_hashes(files),
        }
        native.write(bundle / "manifest.json", report)
        native.write(
            bundle / "configuration.dpapi.json",
            {
                "api_environment": {"DEMO_ENABLED": "true", "IMPORT_BYTE_LIMIT": "4096"},
                "root_env": None,
            },
        )
        original_save = native.save_secret
        original_copy = native.shutil.copytree

        def remember():
            intent = native.load_secret(state / "restore-intent.dpapi.json")
            created_roles.append(intent["user"])
            created_databases.append(intent["dbname"])
            return intent

        if interruption == "after-success":

            def interrupted_save(path, value):
                if path.name == "config.dpapi.json":
                    raise native.SafeError("Synthetic interruption after full successful restore")
                original_save(path, value)

            monkeypatch.setattr(native, "save_secret", interrupted_save)
        else:

            def interrupted_copy(*args, **kwargs):
                raise native.SafeError("Synthetic interruption before storage copy")

            monkeypatch.setattr(native.shutil, "copytree", interrupted_copy)
        with pytest.raises(native.SafeError, match="Synthetic interruption"):
            native.restore(state, bundle, folder, new_target=True)
        first = remember()
        assert len(restores) == 1
        monkeypatch.setattr(native, "save_secret", original_save)
        monkeypatch.setattr(native.shutil, "copytree", original_copy)
        if interruption == "partial-storage":
            with pytest.raises(native.SafeError, match="No restore replay"):
                native.restore(state, bundle, folder)
            assert len(restores) == 1
            native.restore(state, bundle, folder, new_target=True)
            assert remember()["dbname"] != first["dbname"]
            assert len(restores) == 2
        else:
            native.restore(state, bundle, folder)
            assert remember()["dbname"] == first["dbname"]
            assert len(restores) == 1
        native.restore(state, bundle, folder)  # confirmed no-op retry
        assert len(restores) == (2 if interruption == "partial-storage" else 1)
        config = native.load_secret(state / "config.dpapi.json")
        native.verify_copy(config, report)
        intent_path = state / "restore-intent.dpapi.json"
        saved_intent = native.load_secret(intent_path)
        intent_path.unlink()  # simulate a missing local reservation, not a DB change
        with pytest.raises(native.SafeError, match="no matching durable intent"):
            native.restore(state, bundle, folder)
        assert len(restores) == (2 if interruption == "partial-storage" else 1)
        original_save(intent_path, saved_intent)
        assert config["settings"]["IMPORT_BYTE_LIMIT"] == "4096"
        with psycopg.connect(**{**admin, "dbname": source}) as db:
            native.same_data(snapshot, native.inventory(db))
        # Exercise restored hashes/permissions and Dijkstra as the restricted NEW
        # service role, not the superuser used for the logical restore.
        from fastapi.testclient import TestClient

        from app.db.session import get_admin_session, get_session
        from app.main import app

        target_engine = create_engine(native.environment(config, state)["DATABASE_URL"])
        with target_engine.connect() as conn:
            transaction = conn.begin()
            with Session(conn, join_transaction_mode="create_savepoint") as session:
                app.dependency_overrides[get_session] = lambda: session
                app.dependency_overrides[get_admin_session] = lambda: session
                try:
                    with TestClient(app) as client:
                        places = {p.code: str(p.id) for p in demo.places}
                        payload = {
                            "campus_id": str(demo.campus.id),
                            "source": {"kind": "place", "place_id": places["GATE"]},
                            "destination": {"kind": "place", "place_id": places["LIB"]},
                        }
                        route = client.post("/api/v1/routes", json=payload)
                        assert (
                            route.status_code == 200
                            and route.json()["distance_m"] == 256.88
                            and len(route.json()["segments"]) == 3
                        )
                        assert (
                            client.post(
                                "/api/v1/routes", json={**payload, "cost_mode": "directions_only"}
                            ).status_code
                            == 200
                        )
                        login = client.post(
                            "/api/v1/admin/login",
                            json={"username": "copy-test-owner", "password": actor_password},
                            headers={"Origin": "http://127.0.0.1:5173"},
                        )
                        assert login.status_code == 200
                        path = f"/api/v1/admin/campuses/{demo.campus.id}/drafts"
                        assert (
                            client.post(
                                path, headers={"Origin": "http://127.0.0.1:5173"}
                            ).status_code
                            == 403
                        )
                        assert (
                            client.post(
                                path,
                                headers={
                                    "Origin": "http://127.0.0.1:5173",
                                    "X-CSRF-Token": login.json()["csrf_token"],
                                },
                            ).status_code
                            == 201
                        )
                finally:
                    app.dependency_overrides.clear()
            transaction.rollback()
        target_engine.dispose()
        native.verify_copy(config, report)
        # A missing private receipt is detected; no graph/DB repair or replay.
        (Path(config["storage"]) / "private/receipt.json").unlink()
        with pytest.raises(native.SafeError, match="storage hashes"):
            native.verify_copy(config, report)
    finally:
        if (state / "restore-intent.dpapi.json").exists():
            intent = native.load_secret(state / "restore-intent.dpapi.json")
            created_roles.append(intent["user"])
            created_databases.append(intent["dbname"])
        with psycopg.connect(**admin, autocommit=True) as db:
            for name in set(created_databases):
                assert name.startswith(prefix) and re_safe(name)
                db.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
                )
            for name in set(created_roles):
                assert name.startswith(prefix) and re_safe(name)
                db.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))
        get_settings.cache_clear()


def re_safe(name):
    return all(c.isalnum() or c == "_" for c in name)
