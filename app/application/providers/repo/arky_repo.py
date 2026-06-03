from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.arky import (
    ArkyActionPreview,
    ArkyAuditLog,
    ArkyConversation,
    ArkyMessage,
)


class ArkyConversationRepository(ABC):
    @abstractmethod
    async def save(self, conv: ArkyConversation) -> ArkyConversation:
        pass

    @abstractmethod
    async def get_by_id(self, conv_id: UUID, team_id: UUID) -> ArkyConversation | None:
        pass


class ArkyMessageRepository(ABC):
    @abstractmethod
    async def save(self, msg: ArkyMessage) -> ArkyMessage:
        pass

    @abstractmethod
    async def list_by_conversation(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[ArkyMessage]:
        pass


class ArkyAuditLogRepository(ABC):
    @abstractmethod
    async def save(self, log: ArkyAuditLog) -> ArkyAuditLog:
        pass


class ArkyActionPreviewRepository(ABC):
    @abstractmethod
    async def save(self, preview: ArkyActionPreview) -> ArkyActionPreview:
        pass

    @abstractmethod
    async def get_by_id(
        self, preview_id: UUID, team_id: UUID, user_id: UUID
    ) -> ArkyActionPreview | None:
        pass

    @abstractmethod
    async def update(self, preview: ArkyActionPreview) -> ArkyActionPreview:
        pass
