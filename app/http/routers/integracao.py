"""
API de integração chamada pelo Arcaika (autenticada por token de integração).

Prefixo: /integrations/arcaika. O team é sempre o da conexão — nunca do corpo.
"""
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.http.schemas.integracao import (
    CreateObraFromOrcamentoRequest, CreateObraResponse, LinkObraRequest, LinkObraResponse,
    ObraStatusResponse, RegisterWebhookRequest, RegisterWebhookResponse,
    UnlinkedObraItem, UnlinkedObrasResponse,
)
from app.http.schemas.common import MessageResponse
from app.http.dependencies.integracao import IntegrationPrincipal
from app.http.dependencies.services import IntegracaoServiceDep
from app.core.config import settings
from app.domain.errors import ConflictError, DomainError

router = APIRouter(prefix="/integrations/arcaika", tags=["Integração Arcaika"])


@router.post("/obras", response_model=CreateObraResponse, status_code=201)
async def create_obra(
    body: CreateObraFromOrcamentoRequest,
    connection: IntegrationPrincipal,
    svc: IntegracaoServiceDep,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Cria (ou retorna, se já existir) a obra vinculada a um orçamento aceito."""
    try:
        obra, already_existed = await svc.create_obra_from_orcamento(connection, body)
    except DomainError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return CreateObraResponse(
        obra_id=obra.id,
        status=obra.status.value,
        public_url=settings.obra_public_url(obra.id),
        created_at=obra.created_date,
        already_existed=already_existed,
    )


@router.get("/obras/unlinked", response_model=UnlinkedObrasResponse)
async def list_unlinked_obras(
    connection: IntegrationPrincipal,
    svc: IntegracaoServiceDep,
    q: str | None = None,
    page: int = 1,
    limit: int = 20,
):
    """Obras do time ainda sem orçamento Arcaika vinculado (para backfill manual)."""
    limit = max(1, min(limit, 100))
    try:
        itens, has_more = await svc.list_unlinked_obras(connection, page, limit, q)
    except DomainError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return UnlinkedObrasResponse(
        items=[
            UnlinkedObraItem(
                obra_id=o.id, title=o.title, status=o.status.value,
                valor=(o.valor.amount if o.valor else None),
                data_entrega=o.data_entrega, created_at=o.created_date,
                public_url=settings.obra_public_url(o.id),
            ) for o in itens
        ],
        page=page, has_more=has_more,
    )


@router.post("/obras/{obra_id}/link", response_model=LinkObraResponse)
async def link_existing_obra(
    obra_id: UUID,
    body: LinkObraRequest,
    connection: IntegrationPrincipal,
    svc: IntegracaoServiceDep,
):
    """Vincula uma obra já existente (criada antes da conexão) a um orçamento aceito."""
    try:
        obra, already = await svc.link_existing_obra(
            connection, obra_id, body.external_ref.orcamento_id, body.external_ref.solicitacao_id,
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return LinkObraResponse(
        obra_id=obra.id, status=obra.status.value,
        public_url=settings.obra_public_url(obra.id), created_at=obra.created_date,
        already_existed=True, already_linked=already,
    )


@router.get("/obras/{obra_id}", response_model=ObraStatusResponse)
async def get_obra_status(
    obra_id: UUID,
    connection: IntegrationPrincipal,
    svc: IntegracaoServiceDep,
):
    """Status atual da obra (reconciliação/pull para eventos perdidos)."""
    try:
        obra = await svc.get_obra_status(connection, obra_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return ObraStatusResponse(
        obra_id=obra.id,
        status=obra.status.value,
        public_url=settings.obra_public_url(obra.id),
        total_recebido=obra.total_recebido,
        data_entrega=obra.data_entrega,
    )


@router.delete("/obras/{obra_id}/link", response_model=MessageResponse)
async def unlink_obra(
    obra_id: UUID,
    connection: IntegrationPrincipal,
    svc: IntegracaoServiceDep,
):
    """Desvincula a obra do orçamento (não deleta a obra)."""
    try:
        await svc.unlink_obra(connection, obra_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return MessageResponse(message="Vínculo removido")


@router.post("/webhook-endpoint", response_model=RegisterWebhookResponse)
async def register_webhook(
    body: RegisterWebhookRequest,
    connection: IntegrationPrincipal,
    svc: IntegracaoServiceDep,
):
    """Registra a URL de recebimento de webhooks e devolve o segredo de assinatura."""
    try:
        updated = await svc.register_webhook(connection, body.url)
    except DomainError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return RegisterWebhookResponse(
        webhook_url=updated.webhook_url,
        webhook_secret=updated.webhook_secret,
    )
