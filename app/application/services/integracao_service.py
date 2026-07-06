"""
Serviço da integração Arcaika: cria obras a partir de orçamentos aceitos
(idempotente) e grava o evento de outbox na MESMA transação.
"""
from typing import Callable
from uuid import UUID

from app.application.providers.repo.obra_repo import ObraRepository
from app.application.providers.repo.integracao_repo import (
    ArcaikaConnectionRepository, IntegrationEventRepository,
)
from app.application.providers.uow import UOWProvider
from app.application.services.integracao_payload import build_event_data
from app.domain.entities.obra import Obra, ObraOrigem
from app.domain.entities.money import Money
from app.domain.entities.integracao import (
    ArcaikaConnection, ConnectionScope, IntegrationEvent, IntegrationEventType,
)
from app.domain.errors import ConflictError, DomainError


class IntegracaoArcaikaService:
    def __init__(
        self,
        obra_repo: ObraRepository,
        connection_repo: ArcaikaConnectionRepository,
        event_repo: IntegrationEventRepository,
        uow: UOWProvider,
        public_url_for: Callable[[UUID], str],
    ):
        self.obra_repo = obra_repo
        self.connection_repo = connection_repo
        self.event_repo = event_repo
        self.uow = uow
        self.public_url_for = public_url_for

    async def create_obra_from_orcamento(
        self, connection: ArcaikaConnection, req
    ) -> tuple[Obra, bool]:
        """Cria a obra vinculada ao orçamento. Idempotente por orcamento_id.

        Retorna (obra, already_existed).
        """
        connection.ensure_active()
        if not connection.has_scope(ConnectionScope.OBRAS_WRITE):
            raise DomainError("Conexão sem escopo obras:write")

        # Idempotência: 1 obra por orçamento Arcaika.
        existing = await self.obra_repo.get_by_arcaika_orcamento(req.external_ref.orcamento_id)
        if existing is not None:
            return existing, True

        responsavel_id = req.responsavel_id or connection.default_responsavel_id
        categoria_id = req.categoria_id or connection.default_categoria_id

        obra = Obra(
            title=req.title,
            team_id=connection.team_id,
            responsavel_id=responsavel_id,
            description=req.description or "",
            valor=Money(req.valor) if req.valor is not None else None,
            data_entrega=req.data_entrega,
            categoria_id=categoria_id,
            origem=ObraOrigem.ARCAIKA,
            arcaika_orcamento_id=req.external_ref.orcamento_id,
            arcaika_solicitacao_id=req.external_ref.solicitacao_id,
        )
        saved = await self.obra_repo.save(obra)

        # Outbox: evento obra.created na MESMA transação.
        data = build_event_data(saved, self.public_url_for(saved.id))
        event = IntegrationEvent(
            team_id=connection.team_id,
            obra_id=saved.id,
            event_type=IntegrationEventType.OBRA_CREATED,
            payload=data,
        )
        await self.event_repo.save(event)
        await self.uow.commit()
        return saved, False

    async def list_unlinked_obras(
        self, connection: ArcaikaConnection, page: int, limit: int, search: str | None = None,
    ) -> tuple[list[Obra], bool]:
        """Obras do time ainda sem orçamento Arcaika vinculado, paginadas."""
        connection.ensure_active()
        if not connection.has_scope(ConnectionScope.OBRAS_READ):
            raise DomainError("Conexão sem escopo obras:read")
        itens = await self.obra_repo.list_unlinked(connection.team_id, page, limit, search)
        total = await self.obra_repo.count_unlinked(connection.team_id, search)
        has_more = page * limit < total
        return itens, has_more

    async def link_existing_obra(
        self, connection: ArcaikaConnection, obra_id: UUID,
        orcamento_id: UUID, solicitacao_id: UUID,
    ) -> tuple[Obra, bool]:
        """Vincula uma obra já existente a um orçamento aceito. Idempotente pelo par (obra, orçamento).

        Retorna (obra, already_linked).
        """
        connection.ensure_active()
        if not connection.has_scope(ConnectionScope.OBRAS_WRITE):
            raise DomainError("Conexão sem escopo obras:write")

        # get_by_id filtra por team_id → DomainError se de outro team / inexistente.
        obra = await self.obra_repo.get_by_id(obra_id, connection.team_id)

        if obra.arcaika_orcamento_id == orcamento_id:
            return obra, True
        if obra.arcaika_orcamento_id is not None:
            raise ConflictError("Obra já vinculada a outro orçamento")

        outra = await self.obra_repo.get_by_arcaika_orcamento(orcamento_id)
        if outra is not None:
            raise ConflictError("Orçamento já vinculado a outra obra")

        obra.arcaika_orcamento_id = orcamento_id
        obra.arcaika_solicitacao_id = solicitacao_id
        obra.origem = ObraOrigem.ARCAIKA
        saved = await self.obra_repo.save(obra)

        data = build_event_data(saved, self.public_url_for(saved.id))
        event = IntegrationEvent(
            team_id=connection.team_id,
            obra_id=saved.id,
            event_type=IntegrationEventType.OBRA_CREATED,
            payload=data,
        )
        await self.event_repo.save(event)
        await self.uow.commit()
        return saved, False

    async def get_obra_status(self, connection: ArcaikaConnection, obra_id: UUID) -> Obra:
        connection.ensure_active()
        # get_by_id filtra por team_id → impede acesso cross-tenant.
        return await self.obra_repo.get_by_id(obra_id, connection.team_id)

    async def register_webhook(self, connection: ArcaikaConnection, url: str) -> ArcaikaConnection:
        """Registra a URL de recebimento de webhooks do Arcaika. Requer webhooks:manage."""
        connection.ensure_active()
        if not connection.has_scope(ConnectionScope.WEBHOOKS_MANAGE):
            raise DomainError("Conexão sem escopo webhooks:manage")
        connection.set_webhook_url(url)
        saved = await self.connection_repo.save(connection)
        await self.uow.commit()
        return saved

    async def unlink_obra(self, connection: ArcaikaConnection, obra_id: UUID) -> None:
        """Remove o vínculo Arcaika da obra (não deleta a obra)."""
        connection.ensure_active()
        obra = await self.obra_repo.get_by_id(obra_id, connection.team_id)
        obra.arcaika_orcamento_id = None
        obra.arcaika_solicitacao_id = None
        obra.origem = ObraOrigem.MANUAL
        await self.obra_repo.save(obra)
        await self.uow.commit()
