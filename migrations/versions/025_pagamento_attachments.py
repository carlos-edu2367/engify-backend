"""pagamento_attachments

Revision ID: 025_pagamento_attachments
Revises: 024_rh_calendario_eventos
Create Date: 2026-07-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "025_pagamento_attachments"
down_revision: Union[str, None] = "024_rh_calendario_eventos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pagamento_attachments",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("pagamento_id", UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pagamento_id"], ["pagamentos_agendados.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_pagamento_attachments_pagamento", "pagamento_attachments",
        ["pagamento_id", "is_deleted"],
    )
    op.create_index(
        "idx_pagamento_attachments_team", "pagamento_attachments", ["team_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_pagamento_attachments_team", table_name="pagamento_attachments")
    op.drop_index("idx_pagamento_attachments_pagamento", table_name="pagamento_attachments")
    op.drop_table("pagamento_attachments")
