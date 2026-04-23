from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, update, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.notificacao_repo import NotificacaoRepository
from app.domain.entities.notificacao import Notificacao, TipoNotificacao
from app.domain.errors import DomainError
from app.infra.db.models.notificacao_model import NotificacaoModel
from app.infra.db.models.obra_model import ObraModel
from app.infra.db.models.user_model import UserModel


class NotificacaoRepositoryImpl(NotificacaoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, notificacao: Notificacao) -> Notificacao:
        if notificacao.id is None:
            model = NotificacaoModel.from_domain(notificacao)
            self._session.add(model)
            await self._session.flush()
            notificacao.id = model.id
            notificacao.created_at = model.created_at
            return notificacao
        stmt = select(NotificacaoModel).where(NotificacaoModel.id == notificacao.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Notificação não encontrada para atualização")
        model.update_from_domain(notificacao)
        await self._session.flush()
        return model.to_domain()

    async def save_ignore_conflict(self, notificacao: Notificacao) -> None:
        """INSERT ... ON CONFLICT DO NOTHING — idempotente para notificações de prazo."""
        stmt = (
            pg_insert(NotificacaoModel)
            .values(
                id=notificacao.id or uuid4(),
                user_id=notificacao.user_id,
                team_id=notificacao.team_id,
                tipo=notificacao.tipo.value,
                titulo=notificacao.titulo,
                mensagem=notificacao.mensagem,
                reference_id=notificacao.reference_id,
                lida=False,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    NotificacaoModel.user_id,
                    NotificacaoModel.tipo,
                    NotificacaoModel.reference_id,
                ],
                index_where=NotificacaoModel.tipo.in_([
                    TipoNotificacao.PRAZO_7_DIAS.value,
                    TipoNotificacao.PRAZO_1_DIA.value,
                ]),
            )
        )
        await self._session.execute(stmt)

    async def get_by_id(self, id: UUID, user_id: UUID) -> Notificacao:
        stmt = select(NotificacaoModel).where(
            NotificacaoModel.id == id,
            NotificacaoModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Notificação não encontrada")
        return model.to_domain()

    async def list_by_user(self, user_id: UUID, team_id: UUID,
                           page: int, limit: int) -> list[Notificacao]:
        offset = (page - 1) * limit
        stmt = (
            select(NotificacaoModel)
            .where(
                NotificacaoModel.user_id == user_id,
                NotificacaoModel.team_id == team_id,
            )
            .order_by(NotificacaoModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_user(self, user_id: UUID, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(NotificacaoModel).where(
            NotificacaoModel.user_id == user_id,
            NotificacaoModel.team_id == team_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_nao_lidas(self, user_id: UUID, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(NotificacaoModel).where(
            NotificacaoModel.user_id == user_id,
            NotificacaoModel.team_id == team_id,
            NotificacaoModel.lida == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def marcar_todas_lidas(self, user_id: UUID, team_id: UUID) -> None:
        stmt = (
            update(NotificacaoModel)
            .where(
                NotificacaoModel.user_id == user_id,
                NotificacaoModel.team_id == team_id,
                NotificacaoModel.lida == False,  # noqa: E712
            )
            .values(lida=True)
        )
        await self._session.execute(stmt)

    async def list_obras_com_prazo(self, dias: int) -> list[dict]:
        """Retorna obras não-finalizadas cujo prazo é exatamente `dias` dias a partir de hoje.
        Inclui user_id do responsável para criar notificação direcionada."""
        from app.domain.entities.obra import Status
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=dias)
        end = start + timedelta(days=1)

        stmt = (
            select(
                ObraModel.id.label("obra_id"),
                ObraModel.title.label("obra_title"),
                ObraModel.team_id.label("team_id"),
                ObraModel.responsavel_id.label("user_id"),
            )
            .where(
                ObraModel.data_entrega >= start,
                ObraModel.data_entrega < end,
                ObraModel.status != Status.FINALIZADO.value,
                ObraModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        rows = result.mappings().all()
        return [dict(r) for r in rows]
