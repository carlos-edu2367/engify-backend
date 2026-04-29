from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.rh import RegraEncargo


class RhEncargoCachePort(ABC):
    @abstractmethod
    async def get_active_rules(self, team_id: UUID, ano: int, mes: int) -> list[RegraEncargo] | None:
        pass

    @abstractmethod
    async def set_active_rules(self, team_id: UUID, ano: int, mes: int, regras: list[RegraEncargo]) -> None:
        pass

    @abstractmethod
    async def invalidate_team(self, team_id: UUID) -> None:
        pass
