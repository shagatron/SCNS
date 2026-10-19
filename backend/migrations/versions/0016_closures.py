"""Add an independently versioned operational overlay; never seed or rewrite maps."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_closures"
down_revision = "0015_qr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "closure_overlays",
        sa.Column("campus_id", sa.UUID(), sa.ForeignKey("campuses.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("version >= 0"),
    )
    op.create_table(
        "closures",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("campus_id", sa.UUID(), sa.ForeignKey("campuses.id"), nullable=False),
        sa.Column("target_kind", sa.String(24), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("target_checksum", sa.String(64), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_end_at", sa.DateTime(timezone=True)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reopened_at", sa.DateTime(timezone=True)),
        sa.Column("reopen_evidence", sa.String(2000)),
        sa.CheckConstraint(
            "target_kind IN ('outdoor_edge','outdoor_path','indoor_edge','connector')"
        ),
        sa.CheckConstraint("state IN ('closed','unresolved','reopened')"),
        sa.CheckConstraint("estimated_end_at IS NULL OR estimated_end_at > starts_at"),
        sa.CheckConstraint("(state = 'reopened') = (reopened_at IS NOT NULL)"),
    )
    op.create_index("ix_closures_campus_id", "closures", ["campus_id"])
    op.create_table(
        "closure_actions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("campus_id", sa.UUID(), sa.ForeignKey("campuses.id"), nullable=False),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("campus_id", "actor_id", "key"),
    )
    op.execute("""CREATE FUNCTION protect_closure_history() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Operational restriction history must be retained'; END $$;
    CREATE TRIGGER protect_closure_delete BEFORE DELETE ON closures FOR EACH ROW EXECUTE FUNCTION protect_closure_history();
    CREATE TRIGGER protect_closure_action BEFORE UPDATE OR DELETE ON closure_actions FOR EACH ROW EXECUTE FUNCTION protect_closure_history();""")


def downgrade():
    from app.core.config import get_settings

    if get_settings().app_env != "test" and op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM closures)")
    ):
        raise RuntimeError("Non-test downgrade refuses deletion of operational history")
    op.drop_table("closure_actions")
    op.drop_index("ix_closures_campus_id", table_name="closures")
    op.drop_table("closures")
    op.drop_table("closure_overlays")
    op.execute("DROP FUNCTION protect_closure_history()")
