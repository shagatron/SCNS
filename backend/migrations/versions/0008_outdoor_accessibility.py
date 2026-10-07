"""Nullable outdoor measurements preserve unknown until surveyed."""

import sqlalchemy as sa
from alembic import op

revision = "0008_outdoor_accessibility"
down_revision = "0007_graph_node_evidence"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("width_m", sa.Float()),
        ("slope_percent", sa.Float()),
        ("step_count", sa.Integer()),
        ("surface", sa.String(120)),
    ):
        op.add_column("navigation_edges", sa.Column(name, kind, nullable=True))
    for name, expression in (
        ("edge_width", "width_m IS NULL OR (width_m > 0 AND width_m < 'Infinity'::float)"),
        (
            "edge_slope",
            "slope_percent IS NULL OR (slope_percent >= 0 AND slope_percent < 'Infinity'::float)",
        ),
        ("edge_steps", "step_count IS NULL OR step_count >= 0"),
        (
            "edge_step_free_steps",
            "accessibility_status <> 'verified_step_free' OR step_count IS NULL OR step_count = 0",
        ),
    ):
        op.create_check_constraint(name, "navigation_edges", expression)


def downgrade():
    for name in ("edge_width", "edge_slope", "edge_steps", "edge_step_free_steps"):
        op.drop_constraint(name, "navigation_edges", type_="check")
    for name in ("width_m", "slope_percent", "step_count", "surface"):
        op.drop_column("navigation_edges", name)
