"""Unknown local image dimensions cannot accidentally pass a SQL NULL check."""

from alembic import op

revision = "0003_frame_dimensions"
down_revision = "0002_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "indoor_frame_dimensions_required",
        "coordinate_frames",
        "kind <> 'indoor' OR (width_px IS NOT NULL AND height_px IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("indoor_frame_dimensions_required", "coordinate_frames", type_="check")
