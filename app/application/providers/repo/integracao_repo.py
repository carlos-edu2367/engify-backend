"""Interfaces de repositório da integração Arcaika (camada application)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.integracao import ArcaikaConnection, IntegrationEvent


@dataclass
class AuthorizationCodeData:
    """Snapshot de um authorization code lido do repositório (sem o código puro)."""
    id: UUID
    client_id: str
    team_id: UUID
    user_id: UUID
    arcaika_organizacao_id: UUID
    default_responsavel_id: UUID
    default_categoria_id: UUID | None
    redirect_uri: str
    scopes: list[str]
    code_challenge: str
    code_challenge_method: str
    expires_at: datetime
    used: bool


class ArcaikaConnectionRepository(ABC):
    @abstractmethod
    async def save(self, connection: ArcaikaConnection) -> ArcaikaConnection: ...

    @abstractmethod
    async def get_by_id(self, conn_id: UUID) -> ArcaikaConnection | None: ...

    @abstractmethod
    async def get_by_id_for_update(self, conn_id: UUID) -> ArcaikaConnection | None: ...

    @abstractmethod
    async def get_by_team(self, team_id: UUID) -> ArcaikaConnection | None: ...

    @abstractmethod
    async def get_by_organizacao(self, organizacao_id: UUID) -> ArcaikaConnection | None: ...


class IntegrationEventRepository(ABC):
    @abstractmethod
    async def save(self, event: IntegrationEvent) -> IntegrationEvent: ...

    @abstractmethod
    async def list_due(self, limit: int, now: datetime | None = None) -> list[IntegrationEvent]:
        """Eventos PENDING/FAILED cujo next_retry_at já passou."""
        ...


class OAuthAuthorizationCodeRepository(ABC):
    @abstractmethod
    async def create(
        self,
        code_hash: str,
        client_id: str,
        team_id: UUID,
        user_id: UUID,
        arcaika_organizacao_id: UUID,
        default_responsavel_id: UUID,
        default_categoria_id: UUID | None,
        redirect_uri: str,
        scopes: list[str],
        code_challenge: str,
        code_challenge_method: str,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def get_by_code_hash(self, code_hash: str) -> AuthorizationCodeData | None: ...

    @abstractmethod
    async def mark_used(self, code_id: UUID) -> None: ...
