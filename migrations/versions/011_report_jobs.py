"""add report jobs table

Revision ID: 011_report_jobs
Revises: ee543d91b955
Create Date: 2026-04-28 19:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "011_report_jobs"
down_revision: Union[str, None] = "ee543d91b955"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_report_jobs_team_status_created",
        "report_jobs",
        ["team_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_report_jobs_team_type_created",
        "report_jobs",
        ["team_id", "type", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_obras_team_categoria_deleted",
        "obras",
        ["team_id", "categoria_id", "is_deleted"],
        unique=False,
    )
    op.create_index(
        "idx_movimentacoes_recebimentos_obra_data",
        "movimentacoes",
        ["team_id", "obra_id", "type", "is_deleted", "data_movimentacao"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_movimentacoes_recebimentos_obra_data", table_name="movimentacoes")
    op.drop_index("idx_obras_team_categoria_deleted", table_name="obras")
    op.drop_index("idx_report_jobs_team_type_created", table_name="report_jobs")
    op.drop_index("idx_report_jobs_team_status_created", table_name="report_jobs")
    op.drop_table("report_jobs")
