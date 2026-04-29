"""add payroll generation jobs

Revision ID: 017_rh_folha_jobs
Revises: 016_rh_encargos_automaticos_foundation
Create Date: 2026-04-29 01:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "017_rh_folha_jobs"
down_revision: Union[str, None] = "016_rh_encargos_automaticos_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    op.create_table(
        "rh_folha_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pendente"),
        sa.Column("funcionario_ids", JSONB, nullable=True),
        sa.Column("total_funcionarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("falhas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_folha_jobs_team_status_created",
        "rh_folha_jobs",
        ["team_id", "status", "created_at"],
    )
    op.execute("ALTER TABLE rh_folha_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rh_folha_jobs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_select ON rh_folha_jobs
        FOR SELECT
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_insert ON rh_folha_jobs
        FOR INSERT
        WITH CHECK ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_update ON rh_folha_jobs
        FOR UPDATE
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_delete ON rh_folha_jobs
        FOR DELETE
        USING ({_POLICY_USING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_select ON rh_folha_jobs")
    op.execute("DROP POLICY IF EXISTS tenant_insert ON rh_folha_jobs")
    op.execute("DROP POLICY IF EXISTS tenant_update ON rh_folha_jobs")
    op.execute("DROP POLICY IF EXISTS tenant_delete ON rh_folha_jobs")
    op.execute("ALTER TABLE rh_folha_jobs DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_rh_folha_jobs_team_status_created", table_name="rh_folha_jobs")
    op.drop_table("rh_folha_jobs")
