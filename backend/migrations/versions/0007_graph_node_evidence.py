"""Outdoor node provenance notes; does not modify frozen geometry/release pointers."""

import sqlalchemy as sa
from alembic import op

revision = "0007_graph_node_evidence"
down_revision = "f420e55f937e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "navigation_nodes", sa.Column("evidence", sa.Text(), nullable=False, server_default="")
    )


def downgrade():
    op.drop_column("navigation_nodes", "evidence")
