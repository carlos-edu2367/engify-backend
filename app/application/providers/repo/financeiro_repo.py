from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime
from app.domain.entities.financeiro import Movimentacao, PagamentoAgendado, MovimentacaoAttachment
from app.application.dtos.financeiro import MovimentacaoFiltersDTO, PagamentoFiltersDTO


class MovimentacaoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Movimentacao:
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
    async def list_entradas_by_obra(self, obra_id: UUID, team_id: UUID, page: int, limit: int) -> list[Movimentacao]:
        pass

    @abstractmethod
    async def count_entradas_by_obra(self, obra_id: UUID, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def save(self, movimentacao: Movimentacao) -> Movimentacao:
        pass

    @abstractmethod
    async def get_fluxo_caixa(self, team_id: UUID, months: int) -> list[dict]:
        """Retorna agregação mensal de entradas e saídas para o fluxo de caixa."""
        pass


class PagamentoAgendadoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> PagamentoAgendado:
        pass

    @abstractmethod
    async def list_by_ids(self, ids: list[UUID], team_id: UUID) -> list[PagamentoAgendado]:
        """Busca múltiplos pagamentos em uma única query. Seguro por tenant."""
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int, filters: PagamentoFiltersDTO | None = None) -> list[PagamentoAgendado]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID, filters: PagamentoFiltersDTO | None = None) -> int:
        pass

    @abstractmethod
    async def list_overdue(
        self, team_id: UUID, reference: datetime, limit: int,
        created_by_user_id: UUID | None = None,
    ) -> list[PagamentoAgendado]:
        """Pagamentos AGUARDANDO com data_agendada < reference (atrasados).

        Ordenados do mais antigo para o mais recente. Quando
        ``created_by_user_id`` é informado, restringe à autoria (escopo de
        engenheiro)."""
        pass

    @abstractmethod
    async def search(
        self, team_id: UUID, query: str, limit: int,
        created_by_user_id: UUID | None = None,
    ) -> list[PagamentoAgendado]:
        """Busca pagamentos por texto em title/details (case-insensitive).

        Ordenados por data_agendada desc. Seguro por tenant; restringe à
        autoria quando ``created_by_user_id`` é informado."""
        pass

    @abstractmethod
    async def save(self, pagamento: PagamentoAgendado) -> PagamentoAgendado:
        pass

    @abstractmethod
    async def delete_unpaid(self, id: UUID, team_id: UUID, created_by_user_id: UUID | None = None) -> bool:
        """Remove um pagamento pendente do tenant. Retorna False se nao removeu."""
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
