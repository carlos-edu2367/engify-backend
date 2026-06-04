"""add creator metadata to scheduled payments

Revision ID: 020_pagamento_created_by_engineer
Revises: 019_arky_foundation
Create Date: 2026-06-04 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "020_pagamento_created_by_engineer"
down_revision: Union[str, None] = "019_arky_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pagamentos_agendados",
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column("created_by_role", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column("created_by_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column(
            "created_by_engineer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "idx_pagamentos_team_creator_data",
        "pagamentos_agendados",
        ["team_id", "created_by_user_id", "data_agendada"],
    )
    op.create_index(
        "idx_pagamentos_team_engineer_data",
        "pagamentos_agendados",
        ["team_id", "created_by_engineer", "data_agendada"],
    )


def downgrade() -> None:
    op.drop_index("idx_pagamentos_team_engineer_data", table_name="pagamentos_agendados")
    op.drop_index("idx_pagamentos_team_creator_data", table_name="pagamentos_agendados")
    op.drop_column("pagamentos_agendados", "created_by_engineer")
    op.drop_column("pagamentos_agendados", "created_by_name")
    op.drop_column("pagamentos_agendados", "created_by_role")
    op.drop_column("pagamentos_agendados", "created_by_user_id")
