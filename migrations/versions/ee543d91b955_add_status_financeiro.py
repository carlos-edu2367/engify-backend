"""add status financeiro to obras and items

Revision ID: ee543d91b955
Revises: 010
Create Date: 2026-04-28 16:32:13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ee543d91b955'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # String(20) — nenhuma alteração de schema necessária.
    # O novo valor "financeiro" é aceito pelo campo existente.
    # Este script documenta a mudança de domínio.
    pass


def downgrade() -> None:
    # Em downgrade, registros com status="financeiro" precisariam
    # ser migrados de volta para "em_andamento" manualmente.
    op.execute("""
        UPDATE obras SET status = 'em_andamento' WHERE status = 'financeiro';
        UPDATE items SET status = 'em_andamento' WHERE status = 'financeiro';
    """)
