"""Models ORM da integração Arcaika ↔ Engify."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base
from app.domain.entities.integracao import (
    ArcaikaConnection, ConnectionStatus, ConnectionScope,
    IntegrationEvent, EventStatus, IntegrationEventType,
)


class ArcaikaConnectionModel(Base):
    __tablename__ = "arcaika_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    arcaika_organizacao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConnectionStatus.ACTIVE.value
    )
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    default_responsavel_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categorias_obra.id", ondelete="SET NULL"),
        nullable=True,
    )
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    webhook_secret: Mapped[str] = mapped_column(String(200), nullable=False)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> ArcaikaConnection:
        c = object.__new__(ArcaikaConnection)
        c.id = self.id
        c.team_id = self.team_id
        c.arcaika_organizacao_id = self.arcaika_organizacao_id
        c.status = ConnectionStatus(self.status)
        c.scopes = [ConnectionScope(s) for s in (self.scopes or [])]
        c.default_responsavel_id = self.default_responsavel_id
        c.default_categoria_id = self.default_categoria_id
        c.webhook_url = self.webhook_url
        c.webhook_secret = self.webhook_secret
        c.refresh_token_hash = self.refresh_token_hash
        c.created_at = self.created_at
        c.revoked_at = self.revoked_at
        return c

    @classmethod
    def from_domain(cls, c: ArcaikaConnection) -> "ArcaikaConnectionModel":
        return cls(
            id=c.id or uuid.uuid4(),
            team_id=c.team_id,
            arcaika_organizacao_id=c.arcaika_organizacao_id,
            status=c.status.value,
            scopes=[s.value for s in c.scopes],
            default_responsavel_id=c.default_responsavel_id,
            default_categoria_id=c.default_categoria_id,
            webhook_url=c.webhook_url,
            webhook_secret=c.webhook_secret,
            refresh_token_hash=c.refresh_token_hash,
            created_at=c.created_at,
            revoked_at=c.revoked_at,
        )

    def update_from_domain(self, c: ArcaikaConnection) -> None:
        self.status = c.status.value
        self.scopes = [s.value for s in c.scopes]
        self.default_responsavel_id = c.default_responsavel_id
        self.default_categoria_id = c.default_categoria_id
        self.webhook_url = c.webhook_url
        self.webhook_secret = c.webhook_secret
        self.refresh_token_hash = c.refresh_token_hash
        self.revoked_at = c.revoked_at


class IntegrationEventModel(Base):
    __tablename__ = "integration_outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    obra_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obras.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EventStatus.PENDING.value
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Poll do worker: eventos prontos p/ (re)entrega.
        Index("idx_outbox_status_retry", "status", "next_retry_at"),
        Index("idx_outbox_team", "team_id"),
    )

    def to_domain(self) -> IntegrationEvent:
        e = object.__new__(IntegrationEvent)
        e.id = self.id
        e.team_id = self.team_id
        e.obra_id = self.obra_id
        e.event_type = IntegrationEventType(self.event_type)
        e.payload = self.payload
        e.status = EventStatus(self.status)
        e.attempts = self.attempts
        e.next_retry_at = self.next_retry_at
        e.last_error = self.last_error
        e.created_at = self.created_at
        return e

    @classmethod
    def from_domain(cls, e: IntegrationEvent) -> "IntegrationEventModel":
        return cls(
            id=e.id or uuid.uuid4(),
            team_id=e.team_id,
            obra_id=e.obra_id,
            event_type=e.event_type.value,
            payload=e.payload,
            status=e.status.value,
            attempts=e.attempts,
            next_retry_at=e.next_retry_at,
            last_error=e.last_error,
            created_at=e.created_at,
        )

    def update_from_domain(self, e: IntegrationEvent) -> None:
        self.status = e.status.value
        self.attempts = e.attempts
        self.next_retry_at = e.next_retry_at
        self.last_error = e.last_error


class OAuthAuthorizationCodeModel(Base):
    """Authorization code de curta duração do fluxo OAuth (armazenado por hash)."""
    __tablename__ = "oauth_authorization_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    arcaika_organizacao_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    default_responsavel_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    default_categoria_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    code_challenge: Mapped[str] = mapped_column(String(200), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(10), nullable=False, default="S256")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_oauth_codes_expires", "expires_at"),
    )
