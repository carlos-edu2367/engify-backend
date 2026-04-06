from uuid import UUID, uuid4
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.team_repos import TeamRepository, DiaristRepository
from app.domain.entities.team import Team, Diarist
from app.domain.errors import DomainError
from app.infra.db.models.team_model import TeamModel, DiaristModel


class TeamRepositoryImpl(TeamRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Team:
        stmt = select(TeamModel).where(TeamModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Time não encontrado")
        return model.to_domain()

    async def get_by_cnpj(self, cnpj: str) -> Team | None:
        stmt = select(TeamModel).where(TeamModel.cnpj == cnpj)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def save(self, team: Team) -> Team:
        if team.id is None:
            team.id = uuid4()
            model = TeamModel.from_domain(team)
            self._session.add(model)
        else:
            stmt = select(TeamModel).where(TeamModel.id == team.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Time não encontrado para atualização")
            model.update_from_domain(team)
        await self._session.flush()
        return model.to_domain()


class DiaristRepositoryImpl(DiaristRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Diarist:
        stmt = select(DiaristModel).where(
            DiaristModel.id == id,
            DiaristModel.is_deleted == False,  # noqa: E712
        )
        if team_id is not None:
            stmt = stmt.where(DiaristModel.team_id == team_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Diarista não encontrado")
        return model.to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Diarist]:
        offset = (page - 1) * limit
        stmt = (
            select(DiaristModel)
            .where(
                DiaristModel.team_id == team_id,
                DiaristModel.is_deleted == False,  # noqa: E712
            )
            .order_by(DiaristModel.nome)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_team(self, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(DiaristModel).where(
            DiaristModel.team_id == team_id,
            DiaristModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, diarist: Diarist) -> Diarist:
        if diarist.id is None:
            diarist.id = uuid4()
            model = DiaristModel.from_domain(diarist)
            self._session.add(model)
        else:
            stmt = select(DiaristModel).where(DiaristModel.id == diarist.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                raise DomainError("Diarista não encontrado para atualização")
            model.update_from_domain(diarist)
        await self._session.flush()
        return model.to_domain()
