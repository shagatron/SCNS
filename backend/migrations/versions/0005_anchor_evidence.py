"""Retain source/verification notes for administrative anchor edits.

Revision ID: 0005_anchor_evidence
Revises: 9fde71668c52
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_anchor_evidence"
down_revision = "9fde71668c52"
branch_labels = None
depends_on = None


def upgrade():
    # Existing immutable releases retain their original fields and checksum. No
    # evidence is invented for old rows; an admin editing one must supply notes.
    op.add_column(
        "place_anchors",
        sa.Column("accessibility_evidence", sa.Text(), server_default="", nullable=False),
    )


def downgrade():
    op.drop_column("place_anchors", "accessibility_evidence")
