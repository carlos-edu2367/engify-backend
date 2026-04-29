from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.rh import LocalPonto


class RhGeofenceCache(ABC):
    @abstractmethod
    async def get_locais(self, team_id: UUID, funcionario_id: UUID) -> list[LocalPonto] | None:
        pass

    @abstractmethod
    async def set_locais(self, team_id: UUID, funcionario_id: UUID, locais: list[LocalPonto]) -> None:
        pass

    @abstractmethod
    async def invalidate(self, team_id: UUID, funcionario_id: UUID) -> None:
        pass
