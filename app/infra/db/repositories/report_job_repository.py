from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.report_job_repo import ReportJobRepository
from app.domain.entities.report_job import ReportJob
from app.domain.errors import DomainError
from app.infra.db.models.report_job_model import ReportJobModel


class ReportJobRepositoryImpl(ReportJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: ReportJob) -> ReportJob:
        stmt = select(ReportJobModel).where(ReportJobModel.id == job.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = ReportJobModel.from_domain(job)
            self._session.add(model)
        else:
            model.update_from_domain(job)
        await self._session.flush()
        return model.to_domain()

    async def get_by_id(self, id: UUID, team_id: UUID) -> ReportJob:
        stmt = select(ReportJobModel).where(
            ReportJobModel.id == id,
            ReportJobModel.team_id == team_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Job de relatorio nao encontrado")
        return model.to_domain()

    async def get_by_id_unscoped(self, id: UUID) -> ReportJob:
        stmt = select(ReportJobModel).where(ReportJobModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Job de relatorio nao encontrado")
        return model.to_domain()
