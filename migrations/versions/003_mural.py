"""add mural_posts and mural_attachments tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-05
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mesma policy usada em 002_enable_rls.py — permite acesso quando:
# 1. app.current_tenant não está definido (migrações, admin direto)
# 2. team_id bate com o tenant da sessão
_POLICY_USING = """
    current_setting('app.current_tenant', true) IS NULL
    OR current_setting('app.current_tenant', true) = ''
    OR team_id = current_setting('app.current_tenant', true)::uuid
""".strip()

_NEW_TABLES = ["mural_posts", "mural_attachments"]


def upgrade() -> None:
    # ── mural_posts ────────────────────────────────────────────────────────────
    op.create_table(
        "mural_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "obra_id", UUID(as_uuid=True),
            sa.ForeignKey("obras.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalizado para RLS sem JOIN com obras em cada query
        sa.Column(
            "team_id", UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        # Lista de UUIDs (strings) dos usuários mencionados
        sa.Column("mentions", JSONB, nullable=False, server_default="[]"),
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
    # Consulta principal: posts da obra, ordenados por data desc
    op.create_index("idx_mural_obra_deleted", "mural_posts", ["obra_id", "is_deleted"])
    # RLS scan por tenant
    op.create_index("idx_mural_team", "mural_posts", ["team_id"])

    # ── mural_attachments ──────────────────────────────────────────────────────
    op.create_table(
        "mural_attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "post_id", UUID(as_uuid=True),
            sa.ForeignKey("mural_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalizado para RLS por tenant sem JOIN extra
        sa.Column(
            "team_id", UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
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
        "idx_mural_attachments_post", "mural_attachments", ["post_id", "is_deleted"]
    )
    op.create_index("idx_mural_attachments_team", "mural_attachments", ["team_id"])

    # ── Row Level Security (mesma estratégia de 002) ───────────────────────────
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


def downgrade() -> None:
    for table in reversed(_NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("mural_attachments")
    op.drop_table("mural_posts")
