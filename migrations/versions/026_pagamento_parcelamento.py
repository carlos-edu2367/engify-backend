"""pagamento parcelamento

Revision ID: 026_pagamento_parcelamento
Revises: 025_pagamento_attachments
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "026_pagamento_parcelamento"
down_revision: Union[str, None] = "025_pagamento_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pagamentos_agendados",
        sa.Column("parcelamento_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column("parcela_numero", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column("parcela_total", sa.SmallInteger(), nullable=True),
    )
    op.create_index(
        "idx_pagamentos_parcelamento",
        "pagamentos_agendados",
        ["parcelamento_id", "parcela_numero"],
    )


def downgrade() -> None:
    op.drop_index("idx_pagamentos_parcelamento", table_name="pagamentos_agendados")
    op.drop_column("pagamentos_agendados", "parcela_total")
    op.drop_column("pagamentos_agendados", "parcela_numero")
    op.drop_column("pagamentos_agendados", "parcelamento_id")
