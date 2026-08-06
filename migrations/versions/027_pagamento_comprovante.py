"""pagamento comprovante

Revision ID: 027_pagamento_comprovante
Revises: 026_pagamento_parcelamento
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "027_pagamento_comprovante"
down_revision: Union[str, None] = "026_pagamento_parcelamento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pagamentos_agendados",
        sa.Column(
            "requires_receipt", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column(
            "receipt_attached", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "movimentacao_attachments",
        sa.Column(
            "kind", sa.String(length=20), nullable=False,
            server_default=sa.text("'documento'"),
        ),
    )
    op.add_column(
        "movimentacao_attachments",
        sa.Column("origem_pagamento_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "idx_pagamentos_comprovante_pendente",
        "pagamentos_agendados",
        ["team_id", "data_agendada"],
        postgresql_where=sa.text("requires_receipt AND NOT receipt_attached"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_pagamentos_comprovante_pendente", table_name="pagamentos_agendados"
    )
    op.drop_column("movimentacao_attachments", "origem_pagamento_id")
    op.drop_column("movimentacao_attachments", "kind")
    op.drop_column("pagamentos_agendados", "receipt_attached")
    op.drop_column("pagamentos_agendados", "requires_receipt")
