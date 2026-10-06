import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.cli.dataset import read_bundle, seed_bundle
from app.core.config import get_settings
from app.db.session import get_session
from app.main import app


@pytest.fixture(scope="session")
def database_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "TEST_DATABASE_URL is required; use make test-integration (real PostGIS required)"
        )
    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_test"):
        pytest.fail("Integration database name must end with _test")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url, isolation_level="REPEATABLE READ")
    yield engine
    engine.dispose()
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    get_settings.cache_clear()


@pytest.fixture
def db(database_engine, monkeypatch):
    monkeypatch.setenv("DEMO_ENABLED", "true")
    get_settings.cache_clear()
    with database_engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    get_settings.cache_clear()


@pytest.fixture
def bundle():
    return read_bundle(Path(__file__).resolve().parents[3] / "data/demo/campus.json")


@pytest.fixture
def seeded(db, bundle):
    return seed_bundle(db, bundle)


@pytest.fixture
def client(db, seeded):
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
