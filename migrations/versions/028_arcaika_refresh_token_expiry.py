"""Add an explicit expiry to Arcaika integration refresh tokens."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_arcaika_refresh_token_expiry"
down_revision: Union[str, None] = "027_pagamento_comprovante"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "arcaika_connections",
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE arcaika_connections "
            "SET refresh_token_expires_at = created_at + interval '90 days' "
            "WHERE refresh_token_hash IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("arcaika_connections", "refresh_token_expires_at")
