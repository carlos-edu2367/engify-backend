"""add interval times to time adjustments

Revision ID: 022_rh_ajuste_intervalo
Revises: 021_beneficio_valor_dia_atribuicao
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "022_rh_ajuste_intervalo"
down_revision: Union[str, None] = "021_beneficio_valor_dia_atribuicao"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rh_ajustes_ponto",
        sa.Column("hora_intervalo_inicio_solicitada", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "rh_ajustes_ponto",
        sa.Column("hora_intervalo_fim_solicitada", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rh_ajustes_ponto", "hora_intervalo_fim_solicitada")
    op.drop_column("rh_ajustes_ponto", "hora_intervalo_inicio_solicitada")
