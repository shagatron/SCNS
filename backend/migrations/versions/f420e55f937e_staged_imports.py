"""staged_imports"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f420e55f937e"
down_revision = "0005_anchor_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "import_bindings",
        sa.Column("entity", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("dataset_revision_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campus_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campus_id", "dataset_revision_id"],
            ["dataset_revisions.campus_id", "dataset_revisions.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_revision_id", "id"),
        sa.UniqueConstraint("dataset_revision_id", "entity", "external_id"),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campus_id", sa.UUID(), nullable=False),
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("uploader_id", sa.UUID(), nullable=False),
        sa.Column("applier_id", sa.UUID(), nullable=True),
        sa.Column("submission_key", sa.String(length=80), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=40), nullable=False),
        sa.Column("filename", sa.String(length=160), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("preview_version", sa.Integer(), nullable=True),
        sa.Column("preview", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("history", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["applier_id"],
            ["admin_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["campus_id"],
            ["campuses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["dataset_revisions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploader_id"],
            ["admin_users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["campus_id", "revision_id"], ["dataset_revisions.campus_id", "dataset_revisions.id"]
        ),
        sa.CheckConstraint(
            "state IN ('uploaded','parsing','preview_ready','validated','committed','failed','cancelled')",
            name="import_state",
        ),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 3", name="import_attempts"),
        sa.CheckConstraint("byte_size > 0", name="import_bytes"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campus_id", "uploader_id", "submission_key"),
    )
    op.create_index(op.f("ix_import_jobs_campus_id"), "import_jobs", ["campus_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_state"), "import_jobs", ["state"], unique=False)

    op.execute(
        "CREATE TRIGGER frozen_guard BEFORE INSERT OR UPDATE OR DELETE ON import_bindings FOR EACH ROW EXECUTE FUNCTION protect_revision_entity()"
    )


def downgrade():
    op.drop_index(op.f("ix_import_jobs_state"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_campus_id"), table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_table("import_bindings")
