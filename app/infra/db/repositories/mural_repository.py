from uuid import UUID, uuid4
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.obra_repo import MuralRepository
from app.domain.entities.obra import MuralPost, MuralAttachment
from app.domain.errors import DomainError
from app.infra.db.models.obra_model import MuralPostModel, MuralAttachmentModel
from app.infra.db.models.user_model import UserModel


class MuralRepositoryImpl(MuralRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_post(self, post: MuralPost) -> MuralPost:
        stmt = select(MuralPostModel).where(MuralPostModel.id == post.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = MuralPostModel.from_domain(post)
            self._session.add(model)
        else:
            model.update_from_domain(post)
        await self._session.flush()
        return model.to_domain()

    async def get_post_by_id(self, post_id: UUID, team_id: UUID) -> MuralPost:
        """Carrega post com attachments (selectinload) e author_nome (JOIN). Sem N+1."""
        stmt = (
            select(MuralPostModel, UserModel.nome.label("author_nome"))
            .outerjoin(UserModel, MuralPostModel.author_id == UserModel.id)
            .options(selectinload(MuralPostModel.attachments))
            .where(
                MuralPostModel.id == post_id,
                MuralPostModel.team_id == team_id,
                MuralPostModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if not row:
            raise DomainError("Post não encontrado")
        post_model, author_nome = row
        post = post_model.to_domain()
        post.author_nome = author_nome
        post.attachments = [a.to_domain() for a in post_model.attachments
                            if not a.is_deleted]
        return post

    async def list_posts(self, obra_id: UUID, page: int, limit: int) -> list[MuralPost]:
        """Lista paginada com JOIN para author_nome e selectinload para attachments. Sem N+1."""
        offset = (page - 1) * limit
        stmt = (
            select(MuralPostModel, UserModel.nome.label("author_nome"))
            .outerjoin(UserModel, MuralPostModel.author_id == UserModel.id)
            .options(selectinload(MuralPostModel.attachments))
            .where(
                MuralPostModel.obra_id == obra_id,
                MuralPostModel.is_deleted == False,  # noqa: E712
            )
            .order_by(MuralPostModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        posts = []
        for post_model, author_nome in result:
            post = post_model.to_domain()
            post.author_nome = author_nome
            post.attachments = [a.to_domain() for a in post_model.attachments
                                 if not a.is_deleted]
            posts.append(post)
        return posts

    async def count_posts(self, obra_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(MuralPostModel)
            .where(
                MuralPostModel.obra_id == obra_id,
                MuralPostModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save_attachment(self, attachment: MuralAttachment) -> MuralAttachment:
        stmt = select(MuralAttachmentModel).where(
            MuralAttachmentModel.id == attachment.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = MuralAttachmentModel.from_domain(attachment)
            self._session.add(model)
        else:
            model.update_from_domain(attachment)
        await self._session.flush()
        return model.to_domain()

    async def list_attachments(self, post_id: UUID) -> list[MuralAttachment]:
        stmt = (
            select(MuralAttachmentModel)
            .where(
                MuralAttachmentModel.post_id == post_id,
                MuralAttachmentModel.is_deleted == False,  # noqa: E712
            )
            .order_by(MuralAttachmentModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def get_attachment(self, attachment_id: UUID, team_id: UUID) -> MuralAttachment:
        stmt = select(MuralAttachmentModel).where(
            MuralAttachmentModel.id == attachment_id,
            MuralAttachmentModel.team_id == team_id,
            MuralAttachmentModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Attachment não encontrado")
        return model.to_domain()
