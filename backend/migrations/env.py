from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.models import (
    Base,
    admin,  # noqa: F401
    connections,  # noqa: F401
    floorplans,  # noqa: F401
    imports,  # noqa: F401
    indoor,  # noqa: F401
    publication,  # noqa: F401
)

config = context.config
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=lambda obj, name, kind, reflected, compare: (
                not (kind == "table" and reflected and name not in target_metadata.tables)
            ),
        )
        with context.begin_transaction():
            context.run_migrations()
