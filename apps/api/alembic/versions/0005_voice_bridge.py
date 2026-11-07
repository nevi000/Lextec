"""voice bridge (Sprachbruecke)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 23:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("case_messages") as b:
        b.add_column(sa.Column("origin", sa.String(length=20), nullable=True))
        b.add_column(sa.Column("original_text", sa.Text(), nullable=True))
        b.add_column(sa.Column("original_language", sa.String(length=5), nullable=True))
    op.create_table(
        "bridge_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("join_token", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=True),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("question_instance_id", sa.String(length=36), nullable=True),
        sa.Column("question_fact_id", sa.String(length=100), nullable=True),
        sa.Column("question_json", sa.JSON(), nullable=True),
        sa.Column("translation_json", sa.JSON(), nullable=True),
        sa.Column("translation_status", sa.String(length=10), nullable=False),
        sa.Column("translation_error", sa.Text(), nullable=True),
        sa.Column("answer_json", sa.JSON(), nullable=True),
        sa.Column("answer_request_id", sa.String(length=64), nullable=True),
        sa.Column("answer_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_bridge_sessions_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bridge_sessions")),
    )
    op.create_index(op.f("ix_bridge_sessions_case_id"), "bridge_sessions", ["case_id"])
    op.create_index(
        op.f("ix_bridge_sessions_token_hash"), "bridge_sessions", ["token_hash"], unique=True
    )
    op.create_table(
        "translation_cache",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("source_lang", sa.String(length=5), nullable=False),
        sa.Column("target_lang", sa.String(length=5), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("translated", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_translation_cache")),
    )


def downgrade() -> None:
    op.drop_table("translation_cache")
    op.drop_index(op.f("ix_bridge_sessions_token_hash"), table_name="bridge_sessions")
    op.drop_index(op.f("ix_bridge_sessions_case_id"), table_name="bridge_sessions")
    op.drop_table("bridge_sessions")
    with op.batch_alter_table("case_messages") as b:
        b.drop_column("original_language")
        b.drop_column("original_text")
        b.drop_column("origin")
