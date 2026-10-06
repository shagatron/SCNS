from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    isolation_level="REPEATABLE READ",
    connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000"},
)


def get_session():
    with Session(engine) as session, session.begin():
        yield session


def get_admin_session():
    # Atomic conditional writes/row locks serialize edits without stale snapshots.
    with (
        Session(engine.execution_options(isolation_level="READ COMMITTED")) as session,
        session.begin(),
    ):
        yield session
