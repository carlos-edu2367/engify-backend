"""add rh abonos de falta (abono individual e em lote lancado pelo RH)

Revision ID: 029_rh_abonos_falta
Revises: 028_arcaika_refresh_token_expiry
Create Date: 2026-09-08 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "029_rh_abonos_falta"
down_revision: Union[str, None] = "028_arcaika_refresh_token_expiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    op.create_table(
        "rh_abonos_falta",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("motivo", sa.String(255), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_abonos_falta_team_funcionario_data",
        "rh_abonos_falta",
        ["team_id", "funcionario_id", "data"],
    )
    op.create_index(
        "idx_rh_abonos_falta_team_data",
        "rh_abonos_falta",
        ["team_id", "data", "is_deleted"],
    )
    op.execute("ALTER TABLE rh_abonos_falta ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rh_abonos_falta FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_select ON rh_abonos_falta
        FOR SELECT
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_insert ON rh_abonos_falta
        FOR INSERT
        WITH CHECK ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_update ON rh_abonos_falta
        FOR UPDATE
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_delete ON rh_abonos_falta
        FOR DELETE
        USING ({_POLICY_USING})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_delete ON rh_abonos_falta")
    op.execute("DROP POLICY IF EXISTS tenant_update ON rh_abonos_falta")
    op.execute("DROP POLICY IF EXISTS tenant_insert ON rh_abonos_falta")
    op.execute("DROP POLICY IF EXISTS tenant_select ON rh_abonos_falta")
    op.drop_index("idx_rh_abonos_falta_team_data", table_name="rh_abonos_falta")
    op.drop_index("idx_rh_abonos_falta_team_funcionario_data", table_name="rh_abonos_falta")
    op.drop_table("rh_abonos_falta")
