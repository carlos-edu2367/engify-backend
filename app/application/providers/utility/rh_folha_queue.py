from abc import ABC, abstractmethod
from uuid import UUID


class RhFolhaQueuePort(ABC):
    @abstractmethod
    async def enqueue_generate_folha(self, job_id: UUID) -> None:
        pass
