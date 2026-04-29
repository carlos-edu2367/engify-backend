"""add RH foundation tables

Revision ID: 012_rh_foundation
Revises: ee543d91b955
Create Date: 2026-04-28
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "012_rh_foundation"
down_revision: Union[str, None] = "ee543d91b955"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()

_RLS_TABLES = [
    "rh_funcionarios",
    "rh_horarios_trabalho",
    "rh_ferias",
    "rh_locais_ponto",
    "rh_registros_ponto",
    "rh_ajustes_ponto",
    "rh_tipos_atestado",
    "rh_atestados",
    "rh_holerites",
    "rh_audit_logs",
    "rh_idempotency_keys",
    "rh_salario_historico",
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
        "rh_funcionarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=False),
        sa.Column("cargo", sa.String(120), nullable=False),
        sa.Column("salario_base_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("salario_base_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("data_admissao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_rh_funcionarios_team_cpf_active",
        "rh_funcionarios",
        ["team_id", "cpf"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_rh_funcionarios_team_user_active",
        "rh_funcionarios",
        ["team_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND user_id IS NOT NULL"),
    )
    op.create_index(
        "idx_rh_funcionarios_team_active_deleted",
        "rh_funcionarios",
        ["team_id", "is_active", "is_deleted"],
    )

    op.create_table(
        "rh_horarios_trabalho",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_rh_horarios_team_funcionario_active",
        "rh_horarios_trabalho",
        ["team_id", "funcionario_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "rh_horario_turnos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("horario_id", UUID(as_uuid=True), sa.ForeignKey("rh_horarios_trabalho.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column("hora_entrada", sa.Time(), nullable=False),
        sa.Column("hora_saida", sa.Time(), nullable=False),
    )
    op.create_index(
        "uq_rh_horario_turnos_horario_dia",
        "rh_horario_turnos",
        ["horario_id", "dia_semana"],
        unique=True,
    )

    op.create_table(
        "rh_ferias",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="solicitado"),
        sa.Column("motivo_rejeicao", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_ferias_team_funcionario_status_periodo",
        "rh_ferias",
        ["team_id", "funcionario_id", "status", "data_inicio", "data_fim"],
    )

    op.create_table(
        "rh_locais_ponto",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("raio_metros", sa.Float(), nullable=False, server_default="100"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_locais_ponto_team_funcionario_deleted",
        "rh_locais_ponto",
        ["team_id", "funcionario_id", "is_deleted"],
    )

    op.create_table(
        "rh_registros_ponto",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="validado"),
        sa.Column("local_ponto_id", UUID(as_uuid=True), sa.ForeignKey("rh_locais_ponto.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_registros_ponto_team_funcionario_timestamp",
        "rh_registros_ponto",
        ["team_id", "funcionario_id", "timestamp"],
    )
    op.create_index(
        "idx_rh_registros_ponto_team_funcionario_status_timestamp",
        "rh_registros_ponto",
        ["team_id", "funcionario_id", "status", "timestamp"],
    )
    op.create_index(
        "idx_rh_registros_ponto_team_timestamp",
        "rh_registros_ponto",
        ["team_id", "timestamp"],
    )

    op.create_table(
        "rh_ajustes_ponto",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_referencia", sa.DateTime(timezone=True), nullable=False),
        sa.Column("justificativa", sa.String(1000), nullable=False),
        sa.Column("hora_entrada_solicitada", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hora_saida_solicitada", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("motivo_rejeicao", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_ajustes_ponto_team_funcionario_status_data",
        "rh_ajustes_ponto",
        ["team_id", "funcionario_id", "status", "data_referencia"],
    )
    op.create_index(
        "idx_rh_ajustes_ponto_team_status_created",
        "rh_ajustes_ponto",
        ["team_id", "status", "created_at"],
    )

    op.create_table(
        "rh_tipos_atestado",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("prazo_entrega_dias", sa.Integer(), nullable=False),
        sa.Column("abona_falta", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("descricao", sa.String(1000), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_tipos_atestado_team_deleted",
        "rh_tipos_atestado",
        ["team_id", "is_deleted"],
    )

    op.create_table(
        "rh_atestados",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo_atestado_id", UUID(as_uuid=True), sa.ForeignKey("rh_tipos_atestado.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("data_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="aguardando_entrega"),
        sa.Column("motivo_rejeicao", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_atestados_team_funcionario_status_periodo",
        "rh_atestados",
        ["team_id", "funcionario_id", "status", "data_inicio", "data_fim"],
    )
    op.create_index(
        "idx_rh_atestados_team_status_created",
        "rh_atestados",
        ["team_id", "status", "created_at"],
    )

    op.create_table(
        "rh_holerites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mes_referencia", sa.Integer(), nullable=False),
        sa.Column("ano_referencia", sa.Integer(), nullable=False),
        sa.Column("salario_base_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("salario_base_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("horas_extras_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("horas_extras_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("descontos_falta_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("descontos_falta_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("acrescimos_manuais_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("acrescimos_manuais_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("descontos_manuais_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("descontos_manuais_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("valor_liquido_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("valor_liquido_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("pagamento_agendado_id", UUID(as_uuid=True), sa.ForeignKey("pagamentos_agendados.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_rh_holerites_team_funcionario_competencia_active",
        "rh_holerites",
        ["team_id", "funcionario_id", "mes_referencia", "ano_referencia"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND status != 'cancelado'"),
    )
    op.create_index(
        "idx_rh_holerites_team_competencia_status",
        "rh_holerites",
        ["team_id", "mes_referencia", "ano_referencia", "status"],
    )

    op.create_table(
        "rh_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("before", JSONB, nullable=True),
        sa.Column("after", JSONB, nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(120), nullable=True),
        sa.Column("ip_hash", sa.String(255), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_rh_audit_logs_team_entity_created",
        "rh_audit_logs",
        ["team_id", "entity_type", "entity_id", "created_at"],
    )
    op.create_index(
        "idx_rh_audit_logs_team_actor_created",
        "rh_audit_logs",
        ["team_id", "actor_user_id", "created_at"],
    )

    op.create_table(
        "rh_idempotency_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_rh_idempotency_keys_team_scope_key",
        "rh_idempotency_keys",
        ["team_id", "scope", "key"],
        unique=True,
    )

    op.create_table(
        "rh_salario_historico",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("funcionario_id", UUID(as_uuid=True), sa.ForeignKey("rh_funcionarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("salario_anterior_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("salario_anterior_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("salario_novo_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("salario_novo_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("changed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    for table in _RLS_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(_RLS_TABLES):
        _disable_rls(table)

    op.drop_table("rh_salario_historico")
    op.drop_index("uq_rh_idempotency_keys_team_scope_key", table_name="rh_idempotency_keys")
    op.drop_table("rh_idempotency_keys")
    op.drop_index("idx_rh_audit_logs_team_actor_created", table_name="rh_audit_logs")
    op.drop_index("idx_rh_audit_logs_team_entity_created", table_name="rh_audit_logs")
    op.drop_table("rh_audit_logs")
    op.drop_index("idx_rh_holerites_team_competencia_status", table_name="rh_holerites")
    op.drop_index("uq_rh_holerites_team_funcionario_competencia_active", table_name="rh_holerites")
    op.drop_table("rh_holerites")
    op.drop_index("idx_rh_atestados_team_status_created", table_name="rh_atestados")
    op.drop_index("idx_rh_atestados_team_funcionario_status_periodo", table_name="rh_atestados")
    op.drop_table("rh_atestados")
    op.drop_index("idx_rh_tipos_atestado_team_deleted", table_name="rh_tipos_atestado")
    op.drop_table("rh_tipos_atestado")
    op.drop_index("idx_rh_ajustes_ponto_team_status_created", table_name="rh_ajustes_ponto")
    op.drop_index("idx_rh_ajustes_ponto_team_funcionario_status_data", table_name="rh_ajustes_ponto")
    op.drop_table("rh_ajustes_ponto")
    op.drop_index("idx_rh_registros_ponto_team_timestamp", table_name="rh_registros_ponto")
    op.drop_index("idx_rh_registros_ponto_team_funcionario_status_timestamp", table_name="rh_registros_ponto")
    op.drop_index("idx_rh_registros_ponto_team_funcionario_timestamp", table_name="rh_registros_ponto")
    op.drop_table("rh_registros_ponto")
    op.drop_index("idx_rh_locais_ponto_team_funcionario_deleted", table_name="rh_locais_ponto")
    op.drop_table("rh_locais_ponto")
    op.drop_index("idx_rh_ferias_team_funcionario_status_periodo", table_name="rh_ferias")
    op.drop_table("rh_ferias")
    op.drop_index("uq_rh_horario_turnos_horario_dia", table_name="rh_horario_turnos")
    op.drop_table("rh_horario_turnos")
    op.drop_index("uq_rh_horarios_team_funcionario_active", table_name="rh_horarios_trabalho")
    op.drop_table("rh_horarios_trabalho")
    op.drop_index("idx_rh_funcionarios_team_active_deleted", table_name="rh_funcionarios")
    op.drop_index("uq_rh_funcionarios_team_user_active", table_name="rh_funcionarios")
    op.drop_index("uq_rh_funcionarios_team_cpf_active", table_name="rh_funcionarios")
    op.drop_table("rh_funcionarios")
