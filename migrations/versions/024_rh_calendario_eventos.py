"""add rh eventos calendario (feriados, ponto facultativo, abono, liberacao antecipada)

Revision ID: 024_rh_calendario_eventos
Revises: 023_arcaika_integration
Create Date: 2026-07-08 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID


revision: str = "024_rh_calendario_eventos"
down_revision: Union[str, None] = "023_arcaika_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    op.create_table(
        "rh_eventos_calendario",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("hora_corte", sa.Time(), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("aplica_todos", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("funcionario_ids", ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_eventos_calendario_team_data",
        "rh_eventos_calendario",
        ["team_id", "data", "is_deleted"],
    )
    op.execute("ALTER TABLE rh_eventos_calendario ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rh_eventos_calendario FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_select ON rh_eventos_calendario
        FOR SELECT
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_insert ON rh_eventos_calendario
        FOR INSERT
        WITH CHECK ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_update ON rh_eventos_calendario
        FOR UPDATE
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_delete ON rh_eventos_calendario
        FOR DELETE
        USING ({_POLICY_USING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_delete ON rh_eventos_calendario")
    op.execute("DROP POLICY IF EXISTS tenant_update ON rh_eventos_calendario")
    op.execute("DROP POLICY IF EXISTS tenant_insert ON rh_eventos_calendario")
    op.execute("DROP POLICY IF EXISTS tenant_select ON rh_eventos_calendario")
    op.drop_index("idx_rh_eventos_calendario_team_data", table_name="rh_eventos_calendario")
    op.drop_table("rh_eventos_calendario")
