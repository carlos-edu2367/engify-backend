from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.report_job import ReportJob


class ReportJobRepository(ABC):
    @abstractmethod
    async def save(self, job: ReportJob) -> ReportJob:
        pass

    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> ReportJob:
        pass

    @abstractmethod
    async def get_by_id_unscoped(self, id: UUID) -> ReportJob:
        pass
