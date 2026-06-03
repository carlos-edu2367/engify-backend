from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.arky_repo import (
    ArkyActionPreviewRepository,
    ArkyAuditLogRepository,
    ArkyConversationRepository,
    ArkyMessageRepository,
)
from app.domain.entities.arky import (
    ArkyActionPreview,
    ArkyAuditLog,
    ArkyConversation,
    ArkyMessage,
)
from app.infra.db.models.arky_model import (
    ArkyActionPreviewModel,
    ArkyAuditLogModel,
    ArkyConversationModel,
    ArkyMessageModel,
)


class ArkyConversationRepositoryImpl(ArkyConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, conv: ArkyConversation) -> ArkyConversation:
        model = ArkyConversationModel.from_domain(conv)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def get_by_id(
        self, conv_id: UUID, team_id: UUID
    ) -> ArkyConversation | None:
        stmt = select(ArkyConversationModel).where(
            ArkyConversationModel.id == conv_id,
            ArkyConversationModel.team_id == team_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None


class ArkyMessageRepositoryImpl(ArkyMessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, msg: ArkyMessage) -> ArkyMessage:
        model = ArkyMessageModel.from_domain(msg)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def list_by_conversation(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[ArkyMessage]:
        stmt = (
            select(ArkyMessageModel)
            .where(ArkyMessageModel.conversation_id == conversation_id)
            .order_by(ArkyMessageModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [r.to_domain() for r in reversed(rows)]


class ArkyAuditLogRepositoryImpl(ArkyAuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, log: ArkyAuditLog) -> ArkyAuditLog:
        model = ArkyAuditLogModel.from_domain(log)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()


class ArkyActionPreviewRepositoryImpl(ArkyActionPreviewRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, preview: ArkyActionPreview) -> ArkyActionPreview:
        model = ArkyActionPreviewModel.from_domain(preview)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def get_by_id(
        self, preview_id: UUID, team_id: UUID, user_id: UUID
    ) -> ArkyActionPreview | None:
        stmt = select(ArkyActionPreviewModel).where(
            ArkyActionPreviewModel.id == preview_id,
            ArkyActionPreviewModel.team_id == team_id,
            ArkyActionPreviewModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def update(self, preview: ArkyActionPreview) -> ArkyActionPreview:
        stmt = select(ArkyActionPreviewModel).where(
            ArkyActionPreviewModel.id == preview.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"ArkyActionPreview {preview.id} not found")
        model.update_from_domain(preview)
        await self._session.flush()
        return model.to_domain()
