"""add payroll charges foundation tables

Revision ID: 016_rh_encargos_automaticos_foundation
Revises: 015_rh_horario_intervalos
Create Date: 2026-04-29 00:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "016_rh_encargos_automaticos_foundation"
down_revision: Union[str, None] = "015_rh_horario_intervalos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()

_RLS_TABLES = [
    "rh_tabelas_progressivas",
    "rh_faixas_encargo",
    "rh_regras_encargo",
    "rh_regra_encargo_aplicabilidades",
    "rh_holerite_itens",
]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_select ON {table}
        FOR SELECT
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_insert ON {table}
        FOR INSERT
        WITH CHECK ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_update ON {table}
        FOR UPDATE
        USING ({_POLICY_USING})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_delete ON {table}
        FOR DELETE
        USING ({_POLICY_USING})
        """
    )


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_select ON {table}")
    op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
    op.execute(f"DROP POLICY IF EXISTS tenant_update ON {table}")
    op.execute(f"DROP POLICY IF EXISTS tenant_delete ON {table}")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "rh_tabelas_progressivas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo", sa.String(80), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.String(1000), nullable=True),
        sa.Column("vigencia_inicio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vigencia_fim", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_tabelas_progressivas_team_status_vigencia",
        "rh_tabelas_progressivas",
        ["team_id", "status", "vigencia_inicio", "vigencia_fim"],
    )
    op.create_index(
        "idx_rh_tabelas_progressivas_team_codigo",
        "rh_tabelas_progressivas",
        ["team_id", "codigo"],
    )

    op.create_table(
        "rh_faixas_encargo",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tabela_progressiva_id", UUID(as_uuid=True), sa.ForeignKey("rh_tabelas_progressivas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("valor_inicial_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("valor_inicial_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("valor_final_amount", sa.Numeric(28, 10), nullable=True),
        sa.Column("valor_final_currency", sa.String(3), nullable=True),
        sa.Column("aliquota", sa.Numeric(10, 4), nullable=False),
        sa.Column("deducao_amount", sa.Numeric(28, 10), nullable=False, server_default="0"),
        sa.Column("deducao_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("calculo_marginal", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "idx_rh_faixas_encargo_tabela_ordem",
        "rh_faixas_encargo",
        ["tabela_progressiva_id", "ordem"],
    )
    op.create_index(
        "idx_rh_faixas_encargo_team_tabela",
        "rh_faixas_encargo",
        ["team_id", "tabela_progressiva_id"],
    )

    op.create_table(
        "rh_regras_encargo",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("regra_grupo_id", UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo", sa.String(80), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.String(1000), nullable=True),
        sa.Column("tipo_calculo", sa.String(30), nullable=False),
        sa.Column("natureza", sa.String(20), nullable=False),
        sa.Column("base_calculo", sa.String(40), nullable=False),
        sa.Column("prioridade", sa.Integer(), nullable=False),
        sa.Column("vigencia_inicio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vigencia_fim", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("valor_fixo_amount", sa.Numeric(28, 10), nullable=True),
        sa.Column("valor_fixo_currency", sa.String(3), nullable=True),
        sa.Column("percentual", sa.Numeric(10, 4), nullable=True),
        sa.Column("tabela_progressiva_id", UUID(as_uuid=True), sa.ForeignKey("rh_tabelas_progressivas.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("teto_amount", sa.Numeric(28, 10), nullable=True),
        sa.Column("teto_currency", sa.String(3), nullable=True),
        sa.Column("piso_amount", sa.Numeric(28, 10), nullable=True),
        sa.Column("piso_currency", sa.String(3), nullable=True),
        sa.Column("arredondamento", sa.String(40), nullable=False, server_default="ROUND_HALF_UP"),
        sa.Column("incide_no_liquido", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("prioridade >= 0", name="ck_rh_regras_encargo_prioridade_non_negative"),
        sa.CheckConstraint("percentual IS NULL OR percentual >= 0", name="ck_rh_regras_encargo_percentual_non_negative"),
        sa.CheckConstraint(
            "vigencia_fim IS NULL OR vigencia_inicio IS NULL OR vigencia_fim >= vigencia_inicio",
            name="ck_rh_regras_encargo_vigencia",
        ),
    )
    op.create_index(
        "idx_rh_regras_encargo_team_status_vigencia",
        "rh_regras_encargo",
        ["team_id", "status", "vigencia_inicio", "vigencia_fim"],
    )
    op.create_index(
        "idx_rh_regras_encargo_team_codigo_status",
        "rh_regras_encargo",
        ["team_id", "codigo", "status"],
    )
    op.create_index(
        "idx_rh_regras_encargo_team_grupo_vigencia",
        "rh_regras_encargo",
        ["team_id", "regra_grupo_id", "vigencia_inicio", "vigencia_fim"],
    )

    op.create_table(
        "rh_regra_encargo_aplicabilidades",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regra_encargo_id", UUID(as_uuid=True), sa.ForeignKey("rh_regras_encargo.id", ondelete="CASCADE"), nullable=False),
        sa.Column("escopo", sa.String(40), nullable=False),
        sa.Column("valor", sa.String(255), nullable=True),
    )
    op.create_index(
        "idx_rh_regra_aplicabilidades_team_regra",
        "rh_regra_encargo_aplicabilidades",
        ["team_id", "regra_encargo_id"],
    )
    op.create_index(
        "idx_rh_regra_aplicabilidades_team_escopo_valor",
        "rh_regra_encargo_aplicabilidades",
        ["team_id", "escopo", "valor"],
    )

    op.create_table(
        "rh_holerite_itens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holerite_id", UUID(as_uuid=True), sa.ForeignKey("rh_holerites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("origem", sa.String(30), nullable=False),
        sa.Column("codigo", sa.String(80), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("natureza", sa.String(20), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("base_amount", sa.Numeric(28, 10), nullable=False, server_default="0"),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("valor_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("valor_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("regra_encargo_id", UUID(as_uuid=True), sa.ForeignKey("rh_regras_encargo.id", ondelete="SET NULL"), nullable=True),
        sa.Column("regra_grupo_id", UUID(as_uuid=True), nullable=True),
        sa.Column("snapshot_regra", JSONB, nullable=True),
        sa.Column("snapshot_calculo", JSONB, nullable=True),
        sa.Column("is_automatico", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_holerite_itens_team_holerite_ordem",
        "rh_holerite_itens",
        ["team_id", "holerite_id", "ordem"],
    )
    op.create_index(
        "idx_rh_holerite_itens_team_func_comp",
        "rh_holerite_itens",
        ["team_id", "funcionario_id", "created_at"],
    )
    op.create_index(
        "idx_rh_holerite_itens_team_regra",
        "rh_holerite_itens",
        ["team_id", "regra_encargo_id"],
    )

    op.add_column("rh_holerites", sa.Column("valor_bruto_amount", sa.Numeric(28, 10), nullable=False, server_default="0"))
    op.add_column("rh_holerites", sa.Column("valor_bruto_currency", sa.String(3), nullable=False, server_default="BRL"))
    op.add_column("rh_holerites", sa.Column("total_proventos_amount", sa.Numeric(28, 10), nullable=False, server_default="0"))
    op.add_column("rh_holerites", sa.Column("total_proventos_currency", sa.String(3), nullable=False, server_default="BRL"))
    op.add_column("rh_holerites", sa.Column("total_descontos_amount", sa.Numeric(28, 10), nullable=False, server_default="0"))
    op.add_column("rh_holerites", sa.Column("total_descontos_currency", sa.String(3), nullable=False, server_default="BRL"))
    op.add_column("rh_holerites", sa.Column("total_informativos_amount", sa.Numeric(28, 10), nullable=False, server_default="0"))
    op.add_column("rh_holerites", sa.Column("total_informativos_currency", sa.String(3), nullable=False, server_default="BRL"))
    op.add_column("rh_holerites", sa.Column("calculation_version", sa.String(40), nullable=True))
    op.add_column("rh_holerites", sa.Column("calculation_hash", sa.String(255), nullable=True))
    op.add_column("rh_holerites", sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "rh_holerites",
        sa.Column("calculated_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    op.execute(
        """
        UPDATE rh_holerites
        SET
            valor_bruto_amount = salario_base_amount + horas_extras_amount + acrescimos_manuais_amount - descontos_falta_amount,
            total_proventos_amount = salario_base_amount + horas_extras_amount + acrescimos_manuais_amount,
            total_descontos_amount = descontos_falta_amount + descontos_manuais_amount,
            total_informativos_amount = 0,
            calculation_version = 'legacy-v1'
        """
    )

    for table in _RLS_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(_RLS_TABLES):
        _disable_rls(table)

    op.drop_constraint("rh_holerites_calculated_by_user_id_fkey", "rh_holerites", type_="foreignkey")
    op.drop_column("rh_holerites", "calculated_by_user_id")
    op.drop_column("rh_holerites", "calculated_at")
    op.drop_column("rh_holerites", "calculation_hash")
    op.drop_column("rh_holerites", "calculation_version")
    op.drop_column("rh_holerites", "total_informativos_currency")
    op.drop_column("rh_holerites", "total_informativos_amount")
    op.drop_column("rh_holerites", "total_descontos_currency")
    op.drop_column("rh_holerites", "total_descontos_amount")
    op.drop_column("rh_holerites", "total_proventos_currency")
    op.drop_column("rh_holerites", "total_proventos_amount")
    op.drop_column("rh_holerites", "valor_bruto_currency")
    op.drop_column("rh_holerites", "valor_bruto_amount")

    op.drop_index("idx_rh_holerite_itens_team_regra", table_name="rh_holerite_itens")
    op.drop_index("idx_rh_holerite_itens_team_func_comp", table_name="rh_holerite_itens")
    op.drop_index("idx_rh_holerite_itens_team_holerite_ordem", table_name="rh_holerite_itens")
    op.drop_table("rh_holerite_itens")

    op.drop_index("idx_rh_regra_aplicabilidades_team_escopo_valor", table_name="rh_regra_encargo_aplicabilidades")
    op.drop_index("idx_rh_regra_aplicabilidades_team_regra", table_name="rh_regra_encargo_aplicabilidades")
    op.drop_table("rh_regra_encargo_aplicabilidades")

    op.drop_index("idx_rh_regras_encargo_team_grupo_vigencia", table_name="rh_regras_encargo")
    op.drop_index("idx_rh_regras_encargo_team_codigo_status", table_name="rh_regras_encargo")
    op.drop_index("idx_rh_regras_encargo_team_status_vigencia", table_name="rh_regras_encargo")
    op.drop_table("rh_regras_encargo")

    op.drop_index("idx_rh_faixas_encargo_team_tabela", table_name="rh_faixas_encargo")
    op.drop_index("idx_rh_faixas_encargo_tabela_ordem", table_name="rh_faixas_encargo")
    op.drop_table("rh_faixas_encargo")

    op.drop_index("idx_rh_tabelas_progressivas_team_codigo", table_name="rh_tabelas_progressivas")
    op.drop_index("idx_rh_tabelas_progressivas_team_status_vigencia", table_name="rh_tabelas_progressivas")
    op.drop_table("rh_tabelas_progressivas")
