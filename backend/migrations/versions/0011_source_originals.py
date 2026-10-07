"""Private original names/media types; preserve existing bytes and checksums."""

import sqlalchemy as sa
from alembic import op

revision = "0011_source_originals"
down_revision = "0010_release_order"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_assets", sa.Column("original_filename", sa.String(160), nullable=True))
    op.add_column("source_assets", sa.Column("media_type", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("source_assets", "media_type")
    op.drop_column("source_assets", "original_filename")
