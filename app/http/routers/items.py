import json
from fastapi import APIRouter, HTTPException, Request
from uuid import UUID

from app.http.schemas.obras import (
    CreateItemRequest, UpdateItemRequest, ItemResponse,
    RegisterItemAttachmentRequest, ItemAttachmentResponse,
)
from app.http.schemas.common import MessageResponse
from app.http.dependencies.auth import CurrentUser, EngineerUser
from app.http.dependencies.services import ItemServiceDep, ObraServiceDep, ItemAttachmentServiceDep
from app.application.dtos.obra import CreateItem, UpdateItem, CreateItemAttachment
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import items_list_key, items_pattern, item_attachments_key, item_attachments_pattern, public_obra_key
from app.core.limiter import limiter

router = APIRouter(prefix="/obras/{obra_id}/items", tags=["Items"])


def _item_to_response(item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        title=item.title,
        descricao=item.description,
        responsavel_id=item.responsavel_id,
        status=item.status,
        obra_id=item.obra_id,
    )


async def _invalidate_items_cache(redis, team_id: UUID, obra_id: UUID) -> None:
    pattern = items_pattern(team_id, obra_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


async def _get_obra_or_404(obra_svc: ObraServiceDep, obra_id: UUID, team_id: UUID):
    try:
        return await obra_svc.get_obra(obra_id, team_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(
    obra_id: UUID,
    body: CreateItemRequest,
    user: EngineerUser,
    item_svc: ItemServiceDep,
    obra_svc: ObraServiceDep,
):
    """Cria um item/tarefa na obra. Restrito a ADMIN e ENG."""
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    dto = CreateItem(
        title=body.title,
        obra_id=obra_id,
        team_id=user.team.id,
        descricao=body.descricao,
        responsavel_id=body.responsavel_id,
    )
    item = await item_svc.create_item(dto)

    redis = get_redis()
    await _invalidate_items_cache(redis, user.team.id, obra_id)
    await redis.delete(public_obra_key(obra_id))
    return _item_to_response(item)


@router.get("", response_model=list[ItemResponse])
async def list_items(
    obra_id: UUID,
    user: CurrentUser,
    item_svc: ItemServiceDep,
    obra_svc: ObraServiceDep,
):
    """Lista items da obra. Cache Redis 5min."""
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    redis = get_redis()
    cache_key = items_list_key(user.team.id, obra_id)

    cached = await redis.get(cache_key)
    if cached:
        return [ItemResponse.model_validate(i) for i in json.loads(cached)]

    items = await item_svc.list_items(obra_id)
    result = [_item_to_response(i) for i in items]
    await redis.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in result]),
        ex=300,
    )
    return result


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    obra_id: UUID,
    item_id: UUID,
    body: UpdateItemRequest,
    user: EngineerUser,
    item_svc: ItemServiceDep,
    obra_svc: ObraServiceDep,
):
    """Atualiza um item. Restrito a ADMIN e ENG."""
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    try:
        item = await item_svc.get_item(item_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    if item.obra_id != obra_id:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    dto = UpdateItem(
        title=body.title,
        descricao=body.descricao,
        responsavel_id=body.responsavel_id,
        status=body.status,
    )
    updated = await item_svc.update_item(dto, item)

    redis = get_redis()
    await _invalidate_items_cache(redis, user.team.id, obra_id)
    await redis.delete(public_obra_key(obra_id))
    return _item_to_response(updated)


@router.delete("/{item_id}", response_model=MessageResponse)
async def delete_item(
    obra_id: UUID,
    item_id: UUID,
    user: EngineerUser,
    item_svc: ItemServiceDep,
    obra_svc: ObraServiceDep,
):
    """Soft-delete de item. Restrito a ADMIN e ENG."""
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    try:
        item = await item_svc.get_item(item_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    if item.obra_id != obra_id:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    await item_svc.delete_item(item)

    redis = get_redis()
    await _invalidate_items_cache(redis, user.team.id, obra_id)
    await redis.delete(public_obra_key(obra_id))
    return MessageResponse(message="Item removido com sucesso")


# ── Item Attachments ──────────────────────────────────────────────────────────

async def _invalidate_attachments_cache(redis, team_id: UUID, item_id: UUID) -> None:
    pattern = item_attachments_pattern(team_id, item_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


def _attachment_to_response(a) -> ItemAttachmentResponse:
    return ItemAttachmentResponse(
        id=a.id,
        item_id=a.item_id,
        file_path=a.file_path,
        file_name=a.file_name,
        content_type=a.content_type,
        created_at=a.created_at,
    )


@router.post("/{item_id}/attachments", response_model=ItemAttachmentResponse, status_code=201)
@limiter.limit("30/minute")
async def register_item_attachment(
    request: Request,
    obra_id: UUID,
    item_id: UUID,
    body: RegisterItemAttachmentRequest,
    user: EngineerUser,
    att_svc: ItemAttachmentServiceDep,
    obra_svc: ObraServiceDep,
):
    """
    Registra um arquivo anexado a um item após upload via Supabase Storage.
    Fluxo: POST /storage/upload-url (resource_type='item') → upload direto → este endpoint.
    Restrito a ADMIN e ENG. Rate limit: 30/min por IP.
    """
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    dto = CreateItemAttachment(
        item_id=item_id,
        team_id=user.team.id,
        file_path=body.file_path,
        file_name=body.file_name,
        content_type=body.content_type,
    )
    try:
        attachment = await att_svc.register(dto)
    except DomainError as e:
        raise HTTPException(status_code=404, detail=str(e))

    redis = get_redis()
    await _invalidate_attachments_cache(redis, user.team.id, item_id)
    await redis.delete(public_obra_key(obra_id))
    return _attachment_to_response(attachment)


@router.get("/{item_id}/attachments", response_model=list[ItemAttachmentResponse])
async def list_item_attachments(
    obra_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    att_svc: ItemAttachmentServiceDep,
    obra_svc: ObraServiceDep,
):
    """Lista attachments de um item. Cache Redis 10min."""
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    redis = get_redis()
    cache_key = item_attachments_key(user.team.id, item_id)
    cached = await redis.get(cache_key)
    if cached:
        return [ItemAttachmentResponse.model_validate(a) for a in json.loads(cached)]

    attachments = await att_svc.list_by_item(item_id)
    result = [_attachment_to_response(a) for a in attachments]
    await redis.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in result]),
        ex=600,
    )
    return result


@router.delete("/{item_id}/attachments/{attachment_id}", response_model=MessageResponse)
async def delete_item_attachment(
    obra_id: UUID,
    item_id: UUID,
    attachment_id: UUID,
    user: EngineerUser,
    att_svc: ItemAttachmentServiceDep,
    obra_svc: ObraServiceDep,
):
    """Soft-delete de um attachment de item. Restrito a ADMIN e ENG."""
    await _get_obra_or_404(obra_svc, obra_id, user.team.id)

    try:
        attachment = await att_svc.get(attachment_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Attachment não encontrado")

    if attachment.item_id != item_id or attachment.team_id != user.team.id:
        raise HTTPException(status_code=404, detail="Attachment não encontrado")

    await att_svc.delete(attachment)

    redis = get_redis()
    await _invalidate_attachments_cache(redis, user.team.id, item_id)
    await redis.delete(public_obra_key(obra_id))
    return MessageResponse(message="Attachment removido com sucesso")
