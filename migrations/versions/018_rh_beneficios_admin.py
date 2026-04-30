"""add rh beneficios admin resource

Revision ID: 018_rh_beneficios_admin
Revises: 017_rh_folha_jobs
Create Date: 2026-04-30 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "018_rh_beneficios_admin"
down_revision: Union[str, None] = "017_rh_folha_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    op.create_table(
        "rh_beneficios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ativo"),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_beneficios_team_status_deleted",
        "rh_beneficios",
        ["team_id", "status", "is_deleted"],
    )
    op.create_index(
        "uq_rh_beneficios_team_nome_active",
        "rh_beneficios",
        ["team_id", "nome"],
        unique=True,
        postgresql_where=sa.text("status = 'ativo' AND is_deleted = false"),
    )
    op.execute("ALTER TABLE rh_beneficios ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rh_beneficios FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_select ON rh_beneficios
        FOR SELECT
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_insert ON rh_beneficios
        FOR INSERT
        WITH CHECK ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_update ON rh_beneficios
        FOR UPDATE
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_delete ON rh_beneficios
        FOR DELETE
        USING ({_POLICY_USING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_delete ON rh_beneficios")
    op.execute("DROP POLICY IF EXISTS tenant_update ON rh_beneficios")
    op.execute("DROP POLICY IF EXISTS tenant_insert ON rh_beneficios")
    op.execute("DROP POLICY IF EXISTS tenant_select ON rh_beneficios")
    op.drop_index("uq_rh_beneficios_team_nome_active", table_name="rh_beneficios")
    op.drop_index("idx_rh_beneficios_team_status_deleted", table_name="rh_beneficios")
    op.drop_table("rh_beneficios")
