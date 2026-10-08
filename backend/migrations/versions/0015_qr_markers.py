"""Operational QR inventory; never seed or mutate map releases."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_qr"
down_revision = "0014_connections"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "qr_markers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("campus_id", sa.UUID(), sa.ForeignKey("campuses.id"), nullable=False),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("node_kind", sa.String(16), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), sa.ForeignKey("releases.id"), nullable=False),
        sa.Column("target_checksum", sa.String(64), nullable=False),
        sa.Column("intended_position", sa.String(2000), nullable=False),
        sa.Column("installation", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("campus_id", "created_by", "key"),
        sa.CheckConstraint("version > 0"),
        sa.CheckConstraint("node_kind IN ('outdoor', 'indoor')"),
        sa.CheckConstraint(
            "state IN ('planned', 'active', 'revoked', 'retired', 'needs_verification')"
        ),
        sa.CheckConstraint("state <> 'active' OR installation ? 'verified_by'"),
    )
    op.create_index("ix_qr_markers_campus_id", "qr_markers", ["campus_id"])
    op.execute("""CREATE FUNCTION protect_qr_delete() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'QR marker history must be retained; revoke or reassign'; END $$;
    CREATE TRIGGER protect_qr_delete BEFORE DELETE ON qr_markers FOR EACH ROW EXECUTE FUNCTION protect_qr_delete();""")


def downgrade():
    from app.core.config import get_settings

    if get_settings().app_env != "test" and op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM qr_markers)")
    ):
        raise RuntimeError("Non-test downgrade refuses deletion of retained QR inventory")
    op.drop_table("qr_markers")
    op.execute("DROP FUNCTION protect_qr_delete()")
