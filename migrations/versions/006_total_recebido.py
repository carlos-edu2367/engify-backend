"""add total_recebido to obras

Revision ID: 006
Revises: 005
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "obras",
        sa.Column(
            "total_recebido",
            sa.Numeric(28, 10),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "idx_obras_team_total_recebido",
        "obras",
        ["team_id", "total_recebido"],
    )


def downgrade() -> None:
    op.drop_index("idx_obras_team_total_recebido", table_name="obras")
    op.drop_column("obras", "total_recebido")
