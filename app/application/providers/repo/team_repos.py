from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.team import Team, Diarist

class TeamRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Team:
        pass

    @abstractmethod
    async def get_by_cnpj(self, cnpj: str) -> Team | None:
        pass

    @abstractmethod
    async def save(self, team: Team) -> Team:
        pass

class DiaristRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Diarist:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Diarist]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def save(self, diarist: Diarist) -> Diarist:
        pass
