import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.arky import (
    ArkyActionPreview,
    ArkyAuditLog,
    ArkyConversation,
    ArkyMessage,
)
from app.infra.db.models.base import Base, TimestampMixin


class ArkyConversationModel(Base, TimestampMixin):
    __tablename__ = "arky_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_arky_conversations_team_user", "team_id", "user_id"),
        Index("idx_arky_conversations_team_created", "team_id", "created_at"),
    )

    def to_domain(self) -> ArkyConversation:
        c = object.__new__(ArkyConversation)
        c.id = self.id
        c.team_id = self.team_id
        c.user_id = self.user_id
        c.created_at = self.created_at
        return c

    @classmethod
    def from_domain(cls, conv: ArkyConversation) -> "ArkyConversationModel":
        return cls(
            id=conv.id,
            team_id=conv.team_id,
            user_id=conv.user_id,
        )


class ArkyMessageModel(Base, TimestampMixin):
    __tablename__ = "arky_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("arky_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_arky_messages_conversation", "conversation_id", "created_at"),
        Index("idx_arky_messages_team", "team_id"),
    )

    def to_domain(self) -> ArkyMessage:
        m = object.__new__(ArkyMessage)
        m.id = self.id
        m.conversation_id = self.conversation_id
        m.team_id = self.team_id
        m.user_id = self.user_id
        m.role = self.role
        m.content = self.content
        m.created_at = self.created_at
        return m

    @classmethod
    def from_domain(cls, msg: ArkyMessage) -> "ArkyMessageModel":
        return cls(
            id=msg.id,
            conversation_id=msg.conversation_id,
            team_id=msg.team_id,
            user_id=msg.user_id,
            role=msg.role,
            content=msg.content,
        )


class ArkyAuditLogModel(Base, TimestampMixin):
    __tablename__ = "arky_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    user_role: Mapped[str] = mapped_column(String(50), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route: Mapped[str] = mapped_column(String(200), nullable=False)
    module: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_family: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tools_called: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tool_params_masked: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rag_chunk_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    action_preview_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_arky_audit_team_created", "team_id", "created_at"),
        Index("idx_arky_audit_user", "user_id"),
        Index("idx_arky_audit_conversation", "conversation_id"),
    )

    def to_domain(self) -> ArkyAuditLog:
        a = object.__new__(ArkyAuditLog)
        a.id = self.id
        a.team_id = self.team_id
        a.user_id = self.user_id
        a.user_role = self.user_role
        a.conversation_id = self.conversation_id
        a.message_id = self.message_id
        a.request_id = self.request_id
        a.route = self.route
        a.module = self.module
        a.intent = self.intent
        a.model_used = self.model_used
        a.model_family = self.model_family
        a.prompt_tokens = self.prompt_tokens
        a.completion_tokens = self.completion_tokens
        a.latency_ms = self.latency_ms
        a.tools_called = self.tools_called or []
        a.tool_params_masked = self.tool_params_masked
        a.rag_chunk_ids = self.rag_chunk_ids or []
        a.action_preview_id = self.action_preview_id
        a.status = self.status
        a.error_code = self.error_code
        a.created_at = self.created_at
        return a

    @classmethod
    def from_domain(cls, log: ArkyAuditLog) -> "ArkyAuditLogModel":
        return cls(
            id=log.id,
            team_id=log.team_id,
            user_id=log.user_id,
            user_role=log.user_role,
            conversation_id=log.conversation_id,
            message_id=log.message_id,
            request_id=log.request_id,
            route=log.route,
            module=log.module,
            intent=log.intent,
            model_used=log.model_used,
            model_family=log.model_family,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            latency_ms=log.latency_ms,
            tools_called=log.tools_called,
            tool_params_masked=log.tool_params_masked,
            rag_chunk_ids=log.rag_chunk_ids,
            action_preview_id=log.action_preview_id,
            status=log.status,
            error_code=log.error_code,
        )


class ArkyActionPreviewModel(Base, TimestampMixin):
    __tablename__ = "arky_action_previews"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_arky_previews_team_status", "team_id", "status"),
        Index("idx_arky_previews_user", "user_id", "status"),
    )

    def to_domain(self) -> ArkyActionPreview:
        p = object.__new__(ArkyActionPreview)
        p.id = self.id
        p.team_id = self.team_id
        p.user_id = self.user_id
        p.conversation_id = self.conversation_id
        p.action_type = self.action_type
        p.payload = self.payload
        p.summary = self.summary
        p.risk_level = self.risk_level
        p.status = self.status
        p.expires_at = self.expires_at
        p.confirmed_at = self.confirmed_at
        p.rejected_at = self.rejected_at
        p.created_at = self.created_at
        return p

    @classmethod
    def from_domain(cls, p: ArkyActionPreview) -> "ArkyActionPreviewModel":
        return cls(
            id=p.id,
            team_id=p.team_id,
            user_id=p.user_id,
            conversation_id=p.conversation_id,
            action_type=p.action_type,
            payload=p.payload,
            summary=p.summary,
            risk_level=p.risk_level,
            status=p.status,
            expires_at=p.expires_at,
            confirmed_at=p.confirmed_at,
            rejected_at=p.rejected_at,
        )

    def update_from_domain(self, p: ArkyActionPreview) -> None:
        self.status = p.status
        self.confirmed_at = p.confirmed_at
        self.rejected_at = p.rejected_at
