from uuid import UUID, uuid4
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.financeiro_repo import (
    MovimentacaoRepository, PagamentoAgendadoRepository, MovimentacaoAttachmentRepository
)
from app.application.dtos.financeiro import MovimentacaoFiltersDTO, PagamentoFiltersDTO
from app.domain.entities.financeiro import Movimentacao, MovimentacaoTypes, PagamentoAgendado, MovimentacaoAttachment
from app.domain.errors import DomainError
from app.infra.db.models.financeiro_model import (
    MovimentacaoModel, PagamentoAgendadoModel, MovimentacaoAttachmentModel
)


class MovimentacaoRepositoryImpl(MovimentacaoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Movimentacao:
        stmt = select(MovimentacaoModel).where(MovimentacaoModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Movimentação não encontrada")
        return model.to_domain()

    def _apply_filters(self, stmt, filters: MovimentacaoFiltersDTO | None):
        if not filters:
            return stmt
        if filters.period_start:
            stmt = stmt.where(MovimentacaoModel.data_movimentacao >= filters.period_start)
        if filters.period_end:
            stmt = stmt.where(MovimentacaoModel.data_movimentacao <= filters.period_end)
        if filters.obra_id:
            stmt = stmt.where(MovimentacaoModel.obra_id == filters.obra_id)
        if filters.classe:
            stmt = stmt.where(MovimentacaoModel.classe == filters.classe.value)
        return stmt

    async def list_by_team(self, team_id: UUID, page: int, limit: int, filters: MovimentacaoFiltersDTO | None = None) -> list[Movimentacao]:
        offset = (page - 1) * limit
        stmt = (
            select(MovimentacaoModel)
            .where(MovimentacaoModel.team_id == team_id)
            .order_by(MovimentacaoModel.data_movimentacao.desc())
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_team(self, team_id: UUID, filters: MovimentacaoFiltersDTO | None = None) -> int:
        stmt = select(func.count()).select_from(MovimentacaoModel).where(
            MovimentacaoModel.team_id == team_id
        )
        stmt = self._apply_filters(stmt, filters)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def list_by_obra(self, obra_id: UUID, team_id: UUID,
                           page: int, limit: int) -> list[Movimentacao]:
        offset = (page - 1) * limit
        stmt = (
            select(MovimentacaoModel)
            .where(
                MovimentacaoModel.obra_id == obra_id,
                MovimentacaoModel.team_id == team_id,
            )
            .order_by(MovimentacaoModel.data_movimentacao.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def list_entradas_by_obra(self, obra_id: UUID, team_id: UUID,
                                    page: int, limit: int) -> list[Movimentacao]:
        offset = (page - 1) * limit
        stmt = (
            select(MovimentacaoModel)
            .where(
                MovimentacaoModel.obra_id == obra_id,
                MovimentacaoModel.team_id == team_id,
                MovimentacaoModel.type == MovimentacaoTypes.ENTRADA.value,
            )
            .order_by(MovimentacaoModel.data_movimentacao.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_entradas_by_obra(self, obra_id: UUID, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(MovimentacaoModel).where(
            MovimentacaoModel.obra_id == obra_id,
            MovimentacaoModel.team_id == team_id,
            MovimentacaoModel.type == MovimentacaoTypes.ENTRADA.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, movimentacao: Movimentacao) -> Movimentacao:
        if movimentacao.id is None:
            movimentacao.id = uuid4()
            model = MovimentacaoModel.from_domain(movimentacao)
            self._session.add(model)
        else:
            stmt = select(MovimentacaoModel).where(MovimentacaoModel.id == movimentacao.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Movimentação não encontrada para atualização")
            model.update_from_domain(movimentacao)
        await self._session.flush()
        return model.to_domain()


class PagamentoAgendadoRepositoryImpl(PagamentoAgendadoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> PagamentoAgendado:
        stmt = select(PagamentoAgendadoModel).where(PagamentoAgendadoModel.id == id)
        if team_id is not None:
            stmt = stmt.where(PagamentoAgendadoModel.team_id == team_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Pagamento não encontrado")
        return model.to_domain()

    async def list_by_ids(self, ids: list[UUID], team_id: UUID) -> list[PagamentoAgendado]:
        if not ids:
            return []
        stmt = (
            select(PagamentoAgendadoModel)
            .where(
                PagamentoAgendadoModel.id.in_(ids),
                PagamentoAgendadoModel.team_id == team_id,
            )
            .order_by(PagamentoAgendadoModel.id)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    def _apply_filters(self, stmt, filters: PagamentoFiltersDTO | None):
        if not filters:
            return stmt
        if filters.status:
            stmt = stmt.where(PagamentoAgendadoModel.status == filters.status.value)
        if filters.obra_id:
            stmt = stmt.where(PagamentoAgendadoModel.obra_id == filters.obra_id)
        return stmt

    async def list_by_team(self, team_id: UUID, page: int, limit: int, filters: PagamentoFiltersDTO | None = None) -> list[PagamentoAgendado]:
        offset = (page - 1) * limit
        stmt = (
            select(PagamentoAgendadoModel)
            .where(PagamentoAgendadoModel.team_id == team_id)
            .order_by(PagamentoAgendadoModel.data_agendada.desc())
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_team(self, team_id: UUID, filters: PagamentoFiltersDTO | None = None) -> int:
        stmt = select(func.count()).select_from(PagamentoAgendadoModel).where(
            PagamentoAgendadoModel.team_id == team_id
        )
        stmt = self._apply_filters(stmt, filters)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, pagamento: PagamentoAgendado) -> PagamentoAgendado:
        if pagamento.id is None:
            pagamento.id = uuid4()
            model = PagamentoAgendadoModel.from_domain(pagamento)
            self._session.add(model)
        else:
            stmt = select(PagamentoAgendadoModel).where(
                PagamentoAgendadoModel.id == pagamento.id
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Pagamento não encontrado para atualização")
            model.update_from_domain(pagamento)
        await self._session.flush()
        return model.to_domain()


class MovimentacaoAttachmentRepositoryImpl(MovimentacaoAttachmentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> MovimentacaoAttachment:
        stmt = select(MovimentacaoAttachmentModel).where(
            MovimentacaoAttachmentModel.id == id,
            MovimentacaoAttachmentModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Anexo não encontrado")
        return model.to_domain()

    async def list_by_movimentacao(self, movimentacao_id: UUID) -> list[MovimentacaoAttachment]:
        stmt = (
            select(MovimentacaoAttachmentModel)
            .where(
                MovimentacaoAttachmentModel.movimentacao_id == movimentacao_id,
                MovimentacaoAttachmentModel.is_deleted == False,  # noqa: E712
            )
            .order_by(MovimentacaoAttachmentModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def save(self, attachment: MovimentacaoAttachment) -> MovimentacaoAttachment:
        if attachment.id is None:
            attachment.id = uuid4()
            model = MovimentacaoAttachmentModel.from_domain(attachment)
            self._session.add(model)
        else:
            stmt = select(MovimentacaoAttachmentModel).where(
                MovimentacaoAttachmentModel.id == attachment.id
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Anexo não encontrado para atualização")
            model.update_from_domain(attachment)
        await self._session.flush()
        return model.to_domain()
