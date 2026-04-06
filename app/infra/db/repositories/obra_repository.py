from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.providers.repo.obra_repo import (
    ObraRepository, DiaryRepository, ItemRepository, ItemAttachmentRepository, ImageRepository
)
from app.domain.entities.obra import Obra, Status, Item, Diaria, ItemAttachment, Image
from app.domain.errors import DomainError
from app.infra.db.models.obra_model import (
    ObraModel, ItemModel, DiaryModel, ItemAttachmentModel, ImageModel
)
from app.infra.db.models.team_model import DiaristModel


class ObraRepositoryImpl(ObraRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Obra:
        stmt = select(ObraModel).where(
            ObraModel.id == id,
            ObraModel.is_deleted == False,  # noqa: E712
        )
        if team_id is not None:
            stmt = stmt.where(ObraModel.team_id == team_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Obra não encontrada")
        return model.to_domain()

    async def get_by_team(self, team_id: UUID, page: int, limit: int) -> list[Obra]:
        offset = (page - 1) * limit
        stmt = (
            select(ObraModel)
            .where(ObraModel.team_id == team_id, ObraModel.is_deleted == False)  # noqa: E712
            .order_by(ObraModel.created_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_team(self, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(ObraModel).where(
            ObraModel.team_id == team_id,
            ObraModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_status(self, team_id: UUID, status: Status,
                            limit: int, page: int) -> list[Obra]:
        offset = (page - 1) * limit
        stmt = (
            select(ObraModel)
            .where(
                ObraModel.team_id == team_id,
                ObraModel.status == status.value,
                ObraModel.is_deleted == False,  # noqa: E712
            )
            .order_by(ObraModel.created_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_status(self, team_id: UUID, status: Status) -> int:
        stmt = select(func.count()).select_from(ObraModel).where(
            ObraModel.team_id == team_id,
            ObraModel.status == status.value,
            ObraModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, obra: Obra) -> Obra:
        if obra.id is None:
            obra.id = uuid4()
            model = ObraModel.from_domain(obra)
            self._session.add(model)
        else:
            stmt = select(ObraModel).where(ObraModel.id == obra.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Obra não encontrada para atualização")
            model.update_from_domain(obra)
        await self._session.flush()
        return model.to_domain()


class ItemRepositoryImpl(ItemRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Item:
        stmt = select(ItemModel).where(
            ItemModel.id == id,
            ItemModel.is_deleted == False,  # noqa: E712
        )
        if team_id is not None:
            stmt = stmt.where(ItemModel.team_id == team_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Item não encontrado")
        return model.to_domain()

    async def list_by_obra(self, obra_id: UUID) -> list[Item]:
        stmt = (
            select(ItemModel)
            .where(ItemModel.obra_id == obra_id, ItemModel.is_deleted == False)  # noqa: E712
            .order_by(ItemModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def save(self, item: Item) -> Item:
        if item.id is None:
            item.id = uuid4()
            model = ItemModel.from_domain(item)
            self._session.add(model)
        else:
            stmt = select(ItemModel).where(ItemModel.id == item.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Item não encontrado para atualização")
            model.update_from_domain(item)
        await self._session.flush()
        return model.to_domain()


class DiaryRepositoryImpl(DiaryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Diaria:
        stmt = (
            select(DiaryModel)
            .options(selectinload(DiaryModel.diarista), selectinload(DiaryModel.obra))
            .where(DiaryModel.id == id, DiaryModel.is_deleted == False)  # noqa: E712
        )
        if team_id is not None:
            stmt = stmt.where(DiaryModel.team_id == team_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Diária não encontrada")
        return model.to_domain()

    async def get_by_period(self, initial_date: datetime, final_date: datetime,
                            team_id: UUID, page: int, limit: int) -> list[Diaria]:
        offset = (page - 1) * limit
        stmt = (
            select(DiaryModel)
            .options(selectinload(DiaryModel.diarista), selectinload(DiaryModel.obra))
            .where(
                DiaryModel.team_id == team_id,
                DiaryModel.data >= initial_date,
                DiaryModel.data <= final_date,
                DiaryModel.is_deleted == False,  # noqa: E712
            )
            .order_by(DiaryModel.data.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_period(self, initial_date: datetime, final_date: datetime,
                              team_id: UUID) -> int:
        stmt = select(func.count()).select_from(DiaryModel).where(
            DiaryModel.team_id == team_id,
            DiaryModel.data >= initial_date,
            DiaryModel.data <= final_date,
            DiaryModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_diarist(self, diarist_id: UUID, page: int, limit: int) -> list[Diaria]:
        offset = (page - 1) * limit
        stmt = (
            select(DiaryModel)
            .options(selectinload(DiaryModel.diarista), selectinload(DiaryModel.obra))
            .where(DiaryModel.diarista_id == diarist_id, DiaryModel.is_deleted == False)  # noqa: E712
            .order_by(DiaryModel.data.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def save(self, diary: Diaria) -> Diaria:
        if diary.id is None:
            diary.id = uuid4()
            model = DiaryModel.from_domain(diary)
            self._session.add(model)
            await self._session.flush()
            return await self.get_by_id(diary.id)
        else:
            stmt = (
                select(DiaryModel)
                .options(selectinload(DiaryModel.diarista), selectinload(DiaryModel.obra))
                .where(DiaryModel.id == diary.id)
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Diária não encontrada para atualização")
            model.update_from_domain(diary)
            await self._session.flush()
            return model.to_domain()


class ItemAttachmentRepositoryImpl(ItemAttachmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> ItemAttachment:
        stmt = select(ItemAttachmentModel).where(
            ItemAttachmentModel.id == id,
            ItemAttachmentModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Anexo não encontrado")
        return model.to_domain()

    async def list_by_item(self, item_id: UUID) -> list[ItemAttachment]:
        stmt = (
            select(ItemAttachmentModel)
            .where(
                ItemAttachmentModel.item_id == item_id,
                ItemAttachmentModel.is_deleted == False,  # noqa: E712
            )
            .order_by(ItemAttachmentModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def save(self, attachment: ItemAttachment) -> ItemAttachment:
        if attachment.id is None:
            attachment.id = uuid4()
            model = ItemAttachmentModel.from_domain(attachment)
            self._session.add(model)
        else:
            stmt = select(ItemAttachmentModel).where(ItemAttachmentModel.id == attachment.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Anexo não encontrado para atualização")
            model.update_from_domain(attachment)
        await self._session.flush()
        return model.to_domain()


class ImageRepositoryImpl(ImageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_obra(self, obra_id: UUID) -> list[Image]:
        stmt = (
            select(ImageModel)
            .where(ImageModel.obra_id == obra_id, ImageModel.is_deleted == False)  # noqa: E712
            .order_by(ImageModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]
