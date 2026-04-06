from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.user import User, SolicitacaoCadastro, RecoveryCode
from app.application.dtos.user import SimpleUserDisplay

class UserRepository(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> User:
        pass

    @abstractmethod
    async def get_by_email_or_cpf(self, email: str = None, cpf: str = None) -> User|None:
        pass

    @abstractmethod
    async def save(user: User) -> User:
        pass

    @abstractmethod
    async def get_by_team_id(self, team_id: UUID) -> list[SimpleUserDisplay]:
        pass

class SolicitacaoRepo(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> SolicitacaoCadastro:
        pass

    @abstractmethod
    async def save(self, id: UUID) -> SolicitacaoCadastro:
        pass


class RecoveryRepo(ABC):

    @abstractmethod
    async def get_by_id(self, id: UUID) -> RecoveryCode:
        pass


    @abstractmethod
    async def get_active_by_user_id(self, user_id: UUID) -> RecoveryCode | None:
        pass

    @abstractmethod
    async def save(self, recovery: RecoveryCode) -> RecoveryCode:
        pass
