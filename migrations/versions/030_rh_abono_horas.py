"""add minutos ao abono do RH (abono de horas devidas, nao so do dia inteiro)

Revision ID: 030_rh_abono_horas
Revises: 029_rh_abonos_falta
Create Date: 2026-09-10 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "030_rh_abono_horas"
down_revision: Union[str, None] = "029_rh_abonos_falta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECK = "ck_rh_abonos_falta_minutos"


def upgrade() -> None:
    # Nulo = abono do dia inteiro, que e o comportamento de todos os abonos ja
    # lancados; por isso a coluna entra sem default e sem backfill.
    op.add_column("rh_abonos_falta", sa.Column("minutos", sa.Integer(), nullable=True))
    op.create_check_constraint(
        _CHECK,
        "rh_abonos_falta",
        "minutos IS NULL OR (minutos >= 1 AND minutos <= 1440)",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK, "rh_abonos_falta", type_="check")
    op.drop_column("rh_abonos_falta", "minutos")
