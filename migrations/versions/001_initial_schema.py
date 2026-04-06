"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-04
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── teams ──────────────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("cnpj", name="uq_teams_cnpj"),
    )
    op.create_index("idx_teams_cnpj", "teams", ["cnpj"])

    # ── diarists ───────────────────────────────────────────────────────────────
    op.create_table(
        "diarists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=False, server_default=""),
        sa.Column("valor_diaria_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("valor_diaria_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("chave_pix", sa.String(255), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_diarists_team_id", "diarists", ["team_id"])
    op.create_index("idx_diarists_team_deleted", "diarists", ["team_id", "is_deleted"])

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("cpf", name="uq_users_cpf"),
    )
    op.create_index("idx_users_team_id", "users", ["team_id"])
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_cpf", "users", ["cpf"])

    # ── solicitacoes_cadastro ──────────────────────────────────────────────────
    op.create_table(
        "solicitacoes_cadastro",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("expiration", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_solicitacoes_email_used", "solicitacoes_cadastro", ["email", "used"])
    op.create_index("idx_solicitacoes_team", "solicitacoes_cadastro", ["team_id"])

    # ── recovery_codes ─────────────────────────────────────────────────────────
    op.create_table(
        "recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("idx_recovery_user_active", "recovery_codes", ["user_id", "used"])

    # ── obras ──────────────────────────────────────────────────────────────────
    op.create_table(
        "obras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("responsavel_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("valor_amount", sa.Numeric(28, 10), nullable=True),
        sa.Column("valor_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="planejamento"),
        sa.Column("created_date", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("data_entrega", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_obras_team_deleted", "obras", ["team_id", "is_deleted"])
    op.create_index("idx_obras_team_status", "obras", ["team_id", "status"])
    op.create_index("idx_obras_team_created", "obras", ["team_id", "created_date"])

    # ── items ──────────────────────────────────────────────────────────────────
    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("obra_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("obras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("responsavel_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planejamento"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_items_obra_deleted", "items", ["obra_id", "is_deleted"])
    op.create_index("idx_items_team_id", "items", ["team_id"])

    # ── item_attachments ───────────────────────────────────────────────────────
    op.create_table(
        "item_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_item_attachments_item", "item_attachments", ["item_id", "is_deleted"])
    op.create_index("idx_item_attachments_team", "item_attachments", ["team_id"])

    # ── images ─────────────────────────────────────────────────────────────────
    op.create_table(
        "images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("obra_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("obras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False, server_default="image/jpeg"),
        sa.Column("bucket", sa.String(100), nullable=False, server_default="engify"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_images_obra", "images", ["obra_id", "is_deleted"])
    op.create_index("idx_images_team", "images", ["team_id"])

    # ── diarias ────────────────────────────────────────────────────────────────
    op.create_table(
        "diarias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("diarista_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("diarists.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("obra_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("obras.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("descricao_diaria", sa.String(1000), nullable=True),
        sa.Column("quantidade", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("data", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_diarias_team_data", "diarias", ["team_id", "data"])
    op.create_index("idx_diarias_diarista", "diarias", ["diarista_id"])
    op.create_index("idx_diarias_obra", "diarias", ["obra_id", "is_deleted"])

    # ── pagamentos_agendados ───────────────────────────────────────────────────
    op.create_table(
        "pagamentos_agendados",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obra_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("obras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("diarist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("diarists.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("details", sa.String(2000), nullable=False, server_default=""),
        sa.Column("valor_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("valor_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("classe", sa.String(20), nullable=False),
        sa.Column("data_agendada", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_cod", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="aguardando"),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_pagamentos_team_data", "pagamentos_agendados", ["team_id", "data_agendada"])
    op.create_index("idx_pagamentos_team_status", "pagamentos_agendados", ["team_id", "status"])
    op.create_index("idx_pagamentos_obra", "pagamentos_agendados", ["obra_id"])

    # ── movimentacoes ──────────────────────────────────────────────────────────
    op.create_table(
        "movimentacoes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obra_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("obras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pagamento_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pagamentos_agendados.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("valor_amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("valor_currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("classe", sa.String(20), nullable=False),
        sa.Column("natureza", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("data_movimentacao", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_movimentacoes_team_data", "movimentacoes", ["team_id", "data_movimentacao"])
    op.create_index("idx_movimentacoes_team_type", "movimentacoes", ["team_id", "type"])
    op.create_index("idx_movimentacoes_obra", "movimentacoes", ["obra_id"])

    # ── pagamento_attachments ──────────────────────────────────────────────────
    op.create_table(
        "pagamento_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pagamento_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pagamentos_agendados.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_pag_attachments_pagamento", "pagamento_attachments",
                    ["pagamento_id", "is_deleted"])
    op.create_index("idx_pag_attachments_team", "pagamento_attachments", ["team_id"])


def downgrade() -> None:
    op.drop_table("pagamento_attachments")
    op.drop_table("movimentacoes")
    op.drop_table("pagamentos_agendados")
    op.drop_table("diarias")
    op.drop_table("images")
    op.drop_table("item_attachments")
    op.drop_table("items")
    op.drop_table("obras")
    op.drop_table("recovery_codes")
    op.drop_table("solicitacoes_cadastro")
    op.drop_table("users")
    op.drop_table("diarists")
    op.drop_table("teams")
