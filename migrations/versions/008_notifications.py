"""add notifications table

Revision ID: 008
Revises: 007
Create Date: 2026-04-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificacoes",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PG_UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", PG_UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("mensagem", sa.String(1000), nullable=False),
        sa.Column("reference_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("lida", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "tipo", "reference_id",
                            name="uq_notif_user_tipo_ref"),
    )

    op.create_index("idx_notificacoes_user_lida", "notificacoes", ["user_id", "lida"])
    op.create_index("idx_notificacoes_team", "notificacoes", ["team_id"])


def downgrade() -> None:
    op.drop_index("idx_notificacoes_team", table_name="notificacoes")
    op.drop_index("idx_notificacoes_user_lida", table_name="notificacoes")
    op.drop_table("notificacoes")
