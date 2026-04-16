"""add lote_info JSONB to movimentacoes

Revision ID: 007
Revises: 006
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "movimentacoes",
        sa.Column("lote_info", JSONB, nullable=True),
    )
    # GIN index para buscas futuras dentro do JSONB (ex: auditoria por lote_id)
    op.create_index(
        "idx_movimentacoes_lote_info",
        "movimentacoes",
        ["lote_info"],
        postgresql_using="gin",
        postgresql_where=sa.text("lote_info IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_movimentacoes_lote_info", table_name="movimentacoes")
    op.drop_column("movimentacoes", "lote_info")
