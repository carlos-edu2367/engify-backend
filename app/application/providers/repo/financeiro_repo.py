from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime
from app.domain.entities.financeiro import Movimentacao, PagamentoAgendado, MovimentacaoAttachment
from app.application.dtos.financeiro import MovimentacaoFiltersDTO, PagamentoFiltersDTO


class MovimentacaoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Movimentacao:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int, filters: MovimentacaoFiltersDTO | None = None) -> list[Movimentacao]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID, filters: MovimentacaoFiltersDTO | None = None) -> int:
        pass

    @abstractmethod
    async def list_by_obra(self, obra_id: UUID, team_id: UUID, page: int, limit: int) -> list[Movimentacao]:
        pass

    @abstractmethod
    async def save(self, movimentacao: Movimentacao) -> Movimentacao:
        pass


class PagamentoAgendadoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> PagamentoAgendado:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int, filters: PagamentoFiltersDTO | None = None) -> list[PagamentoAgendado]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID, filters: PagamentoFiltersDTO | None = None) -> int:
        pass


    @abstractmethod
    async def save(self, pagamento: PagamentoAgendado) -> PagamentoAgendado:
        pass


class MovimentacaoAttachmentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> MovimentacaoAttachment:
        pass

    @abstractmethod
    async def list_by_movimentacao(self, movimentacao_id: UUID) -> list[MovimentacaoAttachment]:
        pass

    @abstractmethod
    async def save(self, attachment: MovimentacaoAttachment) -> MovimentacaoAttachment:
        pass
