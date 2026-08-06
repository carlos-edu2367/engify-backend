from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime
from app.domain.entities.financeiro import Movimentacao, PagamentoAgendado, MovimentacaoAttachment, PagamentoAttachment
from app.application.dtos.financeiro import MovimentacaoFiltersDTO, PagamentoFiltersDTO


class MovimentacaoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID | None = None) -> Movimentacao:
        pass

    @abstractmethod
    async def get_by_pagamento(self, pagamento_id: UUID, team_id: UUID) -> Movimentacao | None:
        """Movimentacao gerada pela baixa deste pagamento, individual ou em lote.

        Procura primeiro por pagamento_id; se nao achar, procura o pagamento
        dentro de lote_info->'lote_ids'. Retorna None se o pagamento ainda nao
        foi baixado."""
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

    @abstractmethod
    async def get_resumo_obra(self, obra_id: UUID, team_id: UUID) -> list[dict]:
        """Agregado financeiro de uma obra, agrupado por (type, classe).

        Filtra obra_id + team_id + is_deleted = false. Cada linha traz as
        chaves: type, classe, total, qtd."""
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
    async def list_by_parcelamento(self, parcelamento_id: UUID, team_id: UUID) -> list[PagamentoAgendado]:
        """Parcelas de um parcelamento, ordenadas por parcela_numero. Seguro por tenant."""
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

    @abstractmethod
    async def get_comprometido_obra(self, obra_id: UUID, team_id: UUID) -> list[dict]:
        """Custo comprometido de uma obra, agrupado por classe.

        Soma pagamentos com status AGUARDANDO. A tabela nao tem is_deleted:
        remocao e hard delete. Cada linha traz: classe, total, qtd."""
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


class PagamentoAttachmentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> PagamentoAttachment:
        pass

    @abstractmethod
    async def list_by_pagamento(self, pagamento_id: UUID) -> list[PagamentoAttachment]:
        pass

    @abstractmethod
    async def list_by_pagamentos(self, pagamento_ids: list[UUID]) -> list[PagamentoAttachment]:
        """Anexos ativos de múltiplos pagamentos numa única query (usado na baixa em lote)."""
        pass

    @abstractmethod
    async def save(self, attachment: PagamentoAttachment) -> PagamentoAttachment:
        pass
