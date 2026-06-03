"""Arky Copilot foundation tables

Revision ID: 019_arky_foundation
Revises: 018_rh_beneficios_admin
Create Date: 2026-06-03 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "019_arky_foundation"
down_revision: Union[str, None] = "018_rh_beneficios_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Arky conversations
    op.create_table(
        "arky_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_arky_conversations_team_user",
        "arky_conversations",
        ["team_id", "user_id"],
    )
    op.create_index(
        "idx_arky_conversations_team_created",
        "arky_conversations",
        ["team_id", "created_at"],
    )

    # Arky messages
    op.create_table(
        "arky_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("arky_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_arky_messages_conversation",
        "arky_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("idx_arky_messages_team", "arky_messages", ["team_id"])

    # Arky audit logs
    op.create_table(
        "arky_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_role", sa.String(50), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("route", sa.String(200), nullable=False),
        sa.Column("module", sa.String(50), nullable=True),
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("model_family", sa.String(50), nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("tools_called", JSONB, nullable=True),
        sa.Column("tool_params_masked", JSONB, nullable=True),
        sa.Column("rag_chunk_ids", JSONB, nullable=True),
        sa.Column("action_preview_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_arky_audit_team_created",
        "arky_audit_logs",
        ["team_id", "created_at"],
    )
    op.create_index("idx_arky_audit_user", "arky_audit_logs", ["user_id"])
    op.create_index(
        "idx_arky_audit_conversation",
        "arky_audit_logs",
        ["conversation_id"],
    )

    # Arky action previews
    op.create_table(
        "arky_action_previews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("risk_level", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_arky_previews_team_status",
        "arky_action_previews",
        ["team_id", "status"],
    )
    op.create_index(
        "idx_arky_previews_user",
        "arky_action_previews",
        ["user_id", "status"],
    )

    # Enable RLS on arky tables (only for tables with team_id)
    _POLICY_USING = """
        current_setting('app.current_tenant', true) IS NULL
        OR current_setting('app.current_tenant', true) = ''
        OR team_id = current_setting('app.current_tenant', true)::uuid
    """.strip()

    for table in ["arky_conversations", "arky_messages", "arky_audit_logs", "arky_action_previews"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_select ON {table} FOR SELECT USING ({_POLICY_USING})"
        )
        op.execute(
            f"CREATE POLICY tenant_insert ON {table} FOR INSERT WITH CHECK ({_POLICY_USING})"
        )
        op.execute(
            f"CREATE POLICY tenant_update ON {table} FOR UPDATE USING ({_POLICY_USING})"
        )
        op.execute(
            f"CREATE POLICY tenant_delete ON {table} FOR DELETE USING ({_POLICY_USING})"
        )


def downgrade() -> None:
    for table in reversed(
        ["arky_conversations", "arky_messages", "arky_audit_logs", "arky_action_previews"]
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_delete ON {table}")

    op.drop_table("arky_action_previews")
    op.drop_table("arky_audit_logs")
    op.drop_table("arky_messages")
    op.drop_table("arky_conversations")
