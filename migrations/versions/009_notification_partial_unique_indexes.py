"""limit notification dedup to deadline alerts

Revision ID: 009
Revises: 008
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_notif_user_tipo_ref", "notificacoes", type_="unique")
    op.create_index(
        "uq_notif_user_tipo_ref_prazo",
        "notificacoes",
        ["user_id", "tipo", "reference_id"],
        unique=True,
        postgresql_where=sa.text("tipo IN ('prazo_7_dias', 'prazo_1_dia')"),
    )


def downgrade() -> None:
    op.drop_index("uq_notif_user_tipo_ref_prazo", table_name="notificacoes")
    op.create_unique_constraint(
        "uq_notif_user_tipo_ref",
        "notificacoes",
        ["user_id", "tipo", "reference_id"],
    )
