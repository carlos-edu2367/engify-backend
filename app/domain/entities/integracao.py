"""
Entidades de domínio da integração Arcaika ↔ Engify (orçamentos ↔ obras).

- `ArcaikaConnection`: vínculo 1:1 entre um `Team` (Engify) e uma `Organizacao`
  (Arcaika), estabelecido via OAuth. Guarda escopos concedidos, o responsável
  padrão para obras criadas pela integração, e os segredos de webhook.
- `IntegrationEvent`: item de outbox. Toda mudança relevante de obra grava um
  evento na MESMA transação; um worker o entrega ao Arcaika depois, com retry.

Nenhuma dessas entidades conhece FastAPI, SQLAlchemy ou o provedor de HTTP —
são puras, como o resto do `domain/`.
"""
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from app.domain.errors import DomainError


class ConnectionStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ConnectionScope(Enum):
    OBRAS_READ = "obras:read"
    OBRAS_WRITE = "obras:write"
    WEBHOOKS_MANAGE = "webhooks:manage"


class EventStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"      # falhou mas ainda será re-tentado
    DEAD = "dead"          # esgotou as tentativas (DLQ)


class IntegrationEventType(Enum):
    OBRA_CREATED = "obra.created"
    OBRA_STATUS_CHANGED = "obra.status_changed"
    OBRA_FINALIZED = "obra.finalized"
    OBRA_RECEBIMENTO_ADDED = "obra.recebimento_added"
    OBRA_DELETED = "obra.deleted"


# Backoff (em segundos) por tentativa. Depois de esgotar, o evento vira DEAD.
# ~0s, 30s, 2m, 10m, 1h, 6h → 6 entregas antes da DLQ.
RETRY_BACKOFF_SECONDS: list[int] = [0, 30, 120, 600, 3600, 21600]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArcaikaConnection:
    """Vínculo consentido entre um time Engify e uma organização Arcaika."""

    def __init__(
        self,
        team_id: UUID,
        arcaika_organizacao_id: UUID,
        scopes: list[ConnectionScope],
        default_responsavel_id: UUID,
        webhook_secret: str,
        id: UUID = None,
        status: ConnectionStatus = ConnectionStatus.ACTIVE,
        default_categoria_id: UUID = None,
        webhook_url: str | None = None,
        refresh_token_hash: str | None = None,
        refresh_token_expires_at: datetime | None = None,
        created_at: datetime = None,
        revoked_at: datetime = None,
    ):
        if not team_id:
            raise DomainError("Conexão exige team_id")
        if not arcaika_organizacao_id:
            raise DomainError("Conexão exige a organização Arcaika vinculada")
        if not default_responsavel_id:
            raise DomainError(
                "Conexão exige um responsável padrão para obras criadas pela integração"
            )
        if not scopes:
            raise DomainError("Conexão exige ao menos um escopo")
        if not webhook_secret:
            raise DomainError("Conexão exige um segredo de webhook")

        self.id = id or uuid4()
        self.team_id = team_id
        self.arcaika_organizacao_id = arcaika_organizacao_id
        self.scopes = scopes
        self.default_responsavel_id = default_responsavel_id
        self.default_categoria_id = default_categoria_id
        self.webhook_secret = webhook_secret
        self.webhook_url = webhook_url
        self.refresh_token_hash = refresh_token_hash
        self.refresh_token_expires_at = refresh_token_expires_at
        self.status = status
        self.created_at = created_at or _now()
        self.revoked_at = revoked_at

    @property
    def is_active(self) -> bool:
        return self.status == ConnectionStatus.ACTIVE

    def has_scope(self, scope: ConnectionScope) -> bool:
        return self.is_active and scope in self.scopes

    def ensure_active(self) -> None:
        if not self.is_active:
            raise DomainError("Conexão Arcaika revogada")

    def set_webhook_url(self, url: str) -> None:
        self.ensure_active()
        if not url or not url.startswith("https://"):
            raise DomainError("URL de webhook deve ser HTTPS")
        self.webhook_url = url

    def rotate_refresh(self, new_hash: str, expires_at: datetime) -> None:
        self.ensure_active()
        self.refresh_token_hash = new_hash
        self.refresh_token_expires_at = expires_at

    def revoke(self) -> None:
        self.status = ConnectionStatus.REVOKED
        self.revoked_at = _now()
        # Invalida o refresh: nenhuma renovação de token é mais possível.
        self.refresh_token_hash = None
        self.refresh_token_expires_at = None


class IntegrationEvent:
    """Item de outbox: um webhook a ser entregue ao Arcaika."""

    def __init__(
        self,
        team_id: UUID,
        obra_id: UUID,
        event_type: IntegrationEventType,
        payload: dict,
        id: UUID = None,
        status: EventStatus = EventStatus.PENDING,
        attempts: int = 0,
        next_retry_at: datetime = None,
        last_error: str | None = None,
        created_at: datetime = None,
    ):
        if not team_id:
            raise DomainError("Evento exige team_id")
        if not obra_id:
            raise DomainError("Evento exige obra_id")
        self.id = id or uuid4()
        self.team_id = team_id
        self.obra_id = obra_id
        self.event_type = event_type
        self.payload = payload
        self.status = status
        self.attempts = attempts
        self.next_retry_at = next_retry_at if next_retry_at is not None else _now()
        self.last_error = last_error
        self.created_at = created_at or _now()

    @property
    def max_attempts(self) -> int:
        return len(RETRY_BACKOFF_SECONDS)

    def mark_delivered(self) -> None:
        self.status = EventStatus.DELIVERED
        self.next_retry_at = None
        self.last_error = None

    def mark_failed(self, error: str, now: datetime = None) -> None:
        """Registra falha e agenda a próxima tentativa (ou manda p/ DLQ)."""
        now = now or _now()
        self.attempts += 1
        self.last_error = (error or "")[:1000]
        if self.attempts >= self.max_attempts:
            self.status = EventStatus.DEAD
            self.next_retry_at = None
            return
        self.status = EventStatus.FAILED
        delay = RETRY_BACKOFF_SECONDS[self.attempts]
        self.next_retry_at = now + timedelta(seconds=delay)

    def is_due(self, now: datetime = None) -> bool:
        """True se o evento está pronto para (re)tentativa de entrega."""
        if self.status not in (EventStatus.PENDING, EventStatus.FAILED):
            return False
        now = now or _now()
        return self.next_retry_at is None or self.next_retry_at <= now
