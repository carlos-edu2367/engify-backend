"""add categorias_obra table and categoria_id to obras

Revision ID: 004
Revises: 344038d20cd5
Create Date: 2026-04-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "344038d20cd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()

_NEW_TABLES = ["categorias_obra"]


def upgrade() -> None:
    # ── categorias_obra ────────────────────────────────────────────────────────
    op.create_table(
        "categorias_obra",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id", UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("cor", sa.String(20), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_categorias_obra_team_deleted", "categorias_obra", ["team_id", "is_deleted"]
    )
    op.create_index(
        "idx_categorias_obra_team_title", "categorias_obra", ["team_id", "title"]
    )

    # ── Row Level Security ─────────────────────────────────────────────────────
    for table in _NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        op.execute(f"""
            CREATE POLICY tenant_select ON {table}
            FOR SELECT
            USING ({_POLICY_USING})
        """)
        op.execute(f"""
            CREATE POLICY tenant_insert ON {table}
            FOR INSERT
            WITH CHECK ({_POLICY_USING})
        """)
        op.execute(f"""
            CREATE POLICY tenant_update ON {table}
            FOR UPDATE
            USING ({_POLICY_USING})
        """)
        op.execute(f"""
            CREATE POLICY tenant_delete ON {table}
            FOR DELETE
            USING ({_POLICY_USING})
        """)

    # ── Adicionar categoria_id em obras ────────────────────────────────────────
    op.add_column(
        "obras",
        sa.Column(
            "categoria_id", UUID(as_uuid=True),
            sa.ForeignKey("categorias_obra.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_obras_categoria_id", "obras", ["categoria_id"])


def downgrade() -> None:
    op.drop_index("idx_obras_categoria_id", table_name="obras")
    op.drop_column("obras", "categoria_id")

    for table in reversed(_NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("idx_categorias_obra_team_title", table_name="categorias_obra")
    op.drop_index("idx_categorias_obra_team_deleted", table_name="categorias_obra")
    op.drop_table("categorias_obra")
