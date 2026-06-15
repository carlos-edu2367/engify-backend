"""add valor_dia to beneficios and beneficio-funcionario assignment table

Revision ID: 021_beneficio_valor_dia_atribuicao
Revises: 020_pagamento_created_by_engineer
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "021_beneficio_valor_dia_atribuicao"
down_revision: Union[str, None] = "020_pagamento_created_by_engineer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    op.add_column(
        "rh_beneficios",
        sa.Column(
            "valor_dia",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
    )

    op.create_table(
        "rh_beneficio_funcionario",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("beneficio_id", UUID(as_uuid=True), sa.ForeignKey("rh_beneficios.id"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ativo"),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_rh_beneficio_funcionario_ativo",
        "rh_beneficio_funcionario",
        ["team_id", "beneficio_id", "funcionario_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "idx_rh_benef_func_team_func",
        "rh_beneficio_funcionario",
        ["team_id", "funcionario_id", "status", "is_deleted"],
    )

    op.execute("ALTER TABLE rh_beneficio_funcionario ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rh_beneficio_funcionario FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_select ON rh_beneficio_funcionario
        FOR SELECT
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_insert ON rh_beneficio_funcionario
        FOR INSERT
        WITH CHECK ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_update ON rh_beneficio_funcionario
        FOR UPDATE
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_delete ON rh_beneficio_funcionario
        FOR DELETE
        USING ({_POLICY_USING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_delete ON rh_beneficio_funcionario")
    op.execute("DROP POLICY IF EXISTS tenant_update ON rh_beneficio_funcionario")
    op.execute("DROP POLICY IF EXISTS tenant_insert ON rh_beneficio_funcionario")
    op.execute("DROP POLICY IF EXISTS tenant_select ON rh_beneficio_funcionario")
    op.drop_index("idx_rh_benef_func_team_func", table_name="rh_beneficio_funcionario")
    op.drop_index("uq_rh_beneficio_funcionario_ativo", table_name="rh_beneficio_funcionario")
    op.drop_table("rh_beneficio_funcionario")
    op.drop_column("rh_beneficios", "valor_dia")
