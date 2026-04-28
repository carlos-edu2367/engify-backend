from abc import ABC, abstractmethod
from uuid import UUID


class CommissionReportQueue(ABC):
    @abstractmethod
    async def enqueue_generate_commission_report(self, job_id: UUID) -> None:
        pass

