"""merge RH and report job heads

Revision ID: 013_merge_rh_and_report_heads
Revises: 011_report_jobs, 012_rh_foundation
Create Date: 2026-04-28
"""
from __future__ import annotations

from typing import Sequence, Union


revision: str = "013_merge_rh_and_report_heads"
down_revision: Union[str, tuple[str, str], None] = ("011_report_jobs", "012_rh_foundation")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
