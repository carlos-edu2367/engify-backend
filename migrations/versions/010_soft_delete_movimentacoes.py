"""add soft delete to movimentacoes

Revision ID: 010
Revises: 009
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "movimentacoes",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "idx_movimentacoes_team_deleted",
        "movimentacoes",
        ["team_id", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("idx_movimentacoes_team_deleted", table_name="movimentacoes")
    op.drop_column("movimentacoes", "is_deleted")
