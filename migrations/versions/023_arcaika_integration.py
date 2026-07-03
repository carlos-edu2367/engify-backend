"""Arcaika integration foundation (orçamentos → obras)

Revision ID: 023_arcaika_integration
Revises: 022_rh_ajuste_intervalo
Create Date: 2026-07-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "023_arcaika_integration"
down_revision: Union[str, None] = "022_rh_ajuste_intervalo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RLS_TABLES = ["arcaika_connections", "integration_outbox_events", "oauth_authorization_codes"]

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()


def upgrade() -> None:
    # ── obras: colunas de origem/rastreabilidade Arcaika ─────────────────────
    op.add_column(
        "obras",
        sa.Column("origem", sa.String(20), nullable=False, server_default="manual"),
    )
    op.add_column("obras", sa.Column("arcaika_orcamento_id", UUID(as_uuid=True), nullable=True))
    op.add_column("obras", sa.Column("arcaika_solicitacao_id", UUID(as_uuid=True), nullable=True))
    op.create_index(
        "uq_obras_arcaika_orcamento",
        "obras",
        ["arcaika_orcamento_id"],
        unique=True,
        postgresql_where=sa.text("arcaika_orcamento_id IS NOT NULL"),
    )

    # ── arcaika_connections ──────────────────────────────────────────────────
    op.create_table(
        "arcaika_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("arcaika_organizacao_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("default_responsavel_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("default_categoria_id", UUID(as_uuid=True), sa.ForeignKey("categorias_obra.id", ondelete="SET NULL"), nullable=True),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("webhook_secret", sa.String(200), nullable=False),
        sa.Column("refresh_token_hash", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── integration_outbox_events ────────────────────────────────────────────
    op.create_table(
        "integration_outbox_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("obra_id", UUID(as_uuid=True), sa.ForeignKey("obras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_outbox_status_retry", "integration_outbox_events", ["status", "next_retry_at"])
    op.create_index("idx_outbox_team", "integration_outbox_events", ["team_id"])

    # ── oauth_authorization_codes ────────────────────────────────────────────
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("client_id", sa.String(100), nullable=False),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("arcaika_organizacao_id", UUID(as_uuid=True), nullable=False),
        sa.Column("default_responsavel_id", UUID(as_uuid=True), nullable=False),
        sa.Column("default_categoria_id", UUID(as_uuid=True), nullable=True),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("scopes", JSONB, nullable=False),
        sa.Column("code_challenge", sa.String(200), nullable=False),
        sa.Column("code_challenge_method", sa.String(10), nullable=False, server_default="S256"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_oauth_codes_expires", "oauth_authorization_codes", ["expires_at"])

    # ── RLS (defesa em profundidade nas tabelas com team_id) ──────────────────
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_select ON {table} FOR SELECT USING ({_POLICY_USING})")
        op.execute(f"CREATE POLICY tenant_insert ON {table} FOR INSERT WITH CHECK ({_POLICY_USING})")
        op.execute(f"CREATE POLICY tenant_update ON {table} FOR UPDATE USING ({_POLICY_USING})")
        op.execute(f"CREATE POLICY tenant_delete ON {table} FOR DELETE USING ({_POLICY_USING})")


def downgrade() -> None:
    for table in reversed(_RLS_TABLES):
        for pol in ("tenant_select", "tenant_insert", "tenant_update", "tenant_delete"):
            op.execute(f"DROP POLICY IF EXISTS {pol} ON {table}")

    op.drop_index("idx_oauth_codes_expires", table_name="oauth_authorization_codes")
    op.drop_table("oauth_authorization_codes")
    op.drop_index("idx_outbox_team", table_name="integration_outbox_events")
    op.drop_index("idx_outbox_status_retry", table_name="integration_outbox_events")
    op.drop_table("integration_outbox_events")
    op.drop_table("arcaika_connections")

    op.drop_index("uq_obras_arcaika_orcamento", table_name="obras")
    op.drop_column("obras", "arcaika_solicitacao_id")
    op.drop_column("obras", "arcaika_orcamento_id")
    op.drop_column("obras", "origem")
