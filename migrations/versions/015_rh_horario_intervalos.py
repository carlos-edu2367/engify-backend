"""add scheduled intervals to work shifts

Revision ID: 015_rh_horario_intervalos
Revises: 014_rh_ponto_geofence_metadata
Create Date: 2026-04-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "015_rh_horario_intervalos"
down_revision: Union[str, None] = "014_rh_ponto_geofence_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rh_horario_intervalos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("turno_id", UUID(as_uuid=True), sa.ForeignKey("rh_horario_turnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fim", sa.Time(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_rh_horario_intervalos_turno_ordem",
        "rh_horario_intervalos",
        ["turno_id", "ordem"],
    )


def downgrade() -> None:
    op.drop_index("idx_rh_horario_intervalos_turno_ordem", table_name="rh_horario_intervalos")
    op.drop_table("rh_horario_intervalos")
