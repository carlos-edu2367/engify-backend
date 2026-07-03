"""
API de integração chamada pelo Arcaika (autenticada por token de integração).

Prefixo: /integrations/arcaika. O team é sempre o da conexão — nunca do corpo.
"""
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app.http.schemas.integracao import (
    CreateObraFromOrcamentoRequest, CreateObraResponse, ObraStatusResponse,
    RegisterWebhookRequest, RegisterWebhookResponse,
)
from app.http.schemas.common import MessageResponse
from app.http.dependencies.integracao import IntegrationPrincipal
from app.http.dependencies.services import IntegracaoServiceDep
from app.core.config import settings
from app.domain.errors import DomainError

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
