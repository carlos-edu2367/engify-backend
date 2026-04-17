from abc import ABC, abstractmethod
from uuid import UUID
from app.domain.entities.notificacao import Notificacao, TipoNotificacao


class NotificacaoRepository(ABC):
    @abstractmethod
    async def save(self, notificacao: Notificacao) -> Notificacao:
        pass

    @abstractmethod
    async def save_ignore_conflict(self, notificacao: Notificacao) -> None:
        """Insere ignorando conflito de (user_id, tipo, reference_id) — para dedup de prazos."""
        pass

    @abstractmethod
    async def get_by_id(self, id: UUID, user_id: UUID) -> Notificacao:
        pass

    @abstractmethod
    async def list_by_user(self, user_id: UUID, team_id: UUID,
                           page: int, limit: int) -> list[Notificacao]:
        pass

    @abstractmethod
    async def count_by_user(self, user_id: UUID, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def count_nao_lidas(self, user_id: UUID, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def marcar_todas_lidas(self, user_id: UUID, team_id: UUID) -> None:
        pass

    @abstractmethod
    async def list_obras_com_prazo(self, dias: int) -> list[dict]:
        """Retorna obras não-finalizadas com data_entrega em exatamente `dias` dias.
        Retorna dicts com user_id, team_id, obra_id, obra_title para evitar joins pesados."""
        pass
