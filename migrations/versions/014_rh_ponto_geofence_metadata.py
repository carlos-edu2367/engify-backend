"""add rh point metadata

Revision ID: 014_rh_ponto_geofence_metadata
Revises: 013_merge_rh_and_report_heads
Create Date: 2026-04-28
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "014_rh_ponto_geofence_metadata"
down_revision: Union[str, None] = "013_merge_rh_and_report_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rh_registros_ponto", sa.Column("client_timestamp", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rh_registros_ponto", sa.Column("gps_accuracy_meters", sa.Float(), nullable=True))
    op.add_column("rh_registros_ponto", sa.Column("device_fingerprint", sa.String(length=255), nullable=True))
    op.add_column("rh_registros_ponto", sa.Column("ip_hash", sa.String(length=255), nullable=True))
    op.add_column("rh_registros_ponto", sa.Column("denial_reason", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("rh_registros_ponto", "denial_reason")
    op.drop_column("rh_registros_ponto", "ip_hash")
    op.drop_column("rh_registros_ponto", "device_fingerprint")
    op.drop_column("rh_registros_ponto", "gps_accuracy_meters")
    op.drop_column("rh_registros_ponto", "client_timestamp")
