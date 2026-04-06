from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.http.schemas.obras import (
    CreateObraRequest, UpdateObraRequest, UpdateStatusRequest,
    ObraResponse, ObraListItem,
    ObraClienteResponse, ItemClienteView, ImageClienteView,
)
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import CurrentUser, EngineerUser, AdminUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import ObraServiceDep, ItemServiceDep, ObraImageServiceDep
from app.application.dtos.obra import CreateObraDTO, EditObraInfo
from app.domain.entities.obra import Status
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import obras_list_key, obra_detail_key, obras_pattern, obra_cliente_key

router = APIRouter(prefix="/obras", tags=["Obras"])


def _obra_to_response(obra) -> ObraResponse:
    return ObraResponse(
        id=obra.id,
        title=obra.title,
        description=obra.description,
        responsavel_id=obra.responsavel_id,
        team_id=obra.team_id,
        status=obra.status,
        valor=obra.valor.amount if obra.valor else None,
        data_entrega=obra.data_entrega,
        created_date=obra.created_date,
    )


def _obra_to_list_item(obra) -> ObraListItem:
    return ObraListItem(
        id=obra.id,
        title=obra.title,
        status=obra.status,
        responsavel_id=obra.responsavel_id,
        valor=obra.valor.amount if obra.valor else None,
        data_entrega=obra.data_entrega,
        created_date=obra.created_date,
    )


async def _invalidate_obras_cache(redis, team_id: UUID) -> None:
    pattern = obras_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=ObraResponse, status_code=201)
async def create_obra(body: CreateObraRequest, user: EngineerUser, svc: ObraServiceDep):
    """Cria uma nova obra. Restrito a ADMIN e ENG."""
    dto = CreateObraDTO(
        title=body.title,
        team_id=user.team.id,
        responsavel_id=body.responsavel_id,
        description=body.description,
        valor=body.valor,
        data_entrega=body.data_entrega,
    )
    obra = await svc.create_obra(dto)
    redis = get_redis()
    await _invalidate_obras_cache(redis, user.team.id)
    return _obra_to_response(obra)


@router.get("", response_model=PaginatedResponse[ObraListItem])
async def list_obras(
    user: CurrentUser,
    pagination: Pagination,
    svc: ObraServiceDep,
    status: str = "all",
):
    """
    Lista obras do time (paginado). Filtra por status opcional.
    Cache Redis 5min.
    """
    status_enum = None
    if status != "all":
        try:
            status_enum = Status(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Status inválido: {status}")

    redis = get_redis()
    cache_key = obras_list_key(user.team.id, pagination.page, pagination.limit, status)
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[ObraListItem].model_validate_json(cached)

    if status_enum:
        obras = await svc.list_by_status(user.team.id, status_enum, pagination.page, pagination.limit)
        total = await svc.count_by_status(user.team.id, status_enum)
    else:
        obras = await svc.list_obras(user.team.id, pagination.page, pagination.limit)
        total = await svc.count_obras(user.team.id)

    items = [_obra_to_list_item(o) for o in obras]
    result = PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


@router.get("/{obra_id}", response_model=ObraResponse)
async def get_obra(obra_id: UUID, user: CurrentUser, svc: ObraServiceDep):
    """Retorna detalhes de uma obra. Cache Redis 5min."""
    redis = get_redis()
    cache_key = obra_detail_key(user.team.id, obra_id)

    cached = await redis.get(cache_key)
    if cached:
        return ObraResponse.model_validate_json(cached)

    try:
        obra = await svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    response = _obra_to_response(obra)
    await redis.set(cache_key, response.model_dump_json(), ex=300)
    return response


@router.put("/{obra_id}", response_model=ObraResponse)
async def update_obra(
    obra_id: UUID,
    body: UpdateObraRequest,
    user: EngineerUser,
    svc: ObraServiceDep,
):
    """Atualiza dados da obra. Restrito a ADMIN e ENG."""
    if not any([body.title, body.responsavel_id, body.description,
                body.valor is not None, body.data_entrega]):
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar")

    try:
        obra = await svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    dto = EditObraInfo(
        title=body.title,
        responsavel_id=body.responsavel_id,
        description=body.description,
        valor=body.valor,
        data_entrega=body.data_entrega,
    )
    updated = await svc.update_obra(obra, dto)
    redis = get_redis()
    await _invalidate_obras_cache(redis, user.team.id)
    return _obra_to_response(updated)


@router.patch("/{obra_id}/status", response_model=ObraResponse)
async def update_obra_status(
    obra_id: UUID,
    body: UpdateStatusRequest,
    user: EngineerUser,
    svc: ObraServiceDep,
):
    """Atualiza o status da obra. Restrito a ADMIN e ENG."""
    try:
        obra = await svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    updated = await svc.update_status(obra, body.status)
    redis = get_redis()
    await _invalidate_obras_cache(redis, user.team.id)
    return _obra_to_response(updated)


@router.delete("/{obra_id}", response_model=MessageResponse)
async def delete_obra(obra_id: UUID, user: AdminUser, svc: ObraServiceDep):
    """Soft-delete da obra. Restrito a ADMIN."""
    try:
        obra = await svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    await svc.delete_obra(obra)
    redis = get_redis()
    await _invalidate_obras_cache(redis, user.team.id)
    return MessageResponse(message="Obra removida com sucesso")


# ── Visão do Cliente ───────────────────────────────────────────────────────────

@router.get("/{obra_id}/cliente", response_model=ObraClienteResponse)
async def get_obra_cliente(
    obra_id: UUID,
    user: CurrentUser,
    svc: ObraServiceDep,
    item_svc: ItemServiceDep,
    image_svc: ObraImageServiceDep,
):
    """
    Visão somente-leitura da obra para o cliente.
    Expõe apenas: status da obra, título, items (título + status) e imagens.
    Não expõe dados financeiros, mural, diárias ou responsáveis.
    Disponível para qualquer membro autenticado do time (preview + cliente).
    Cache Redis 60s.
    """
    redis = get_redis()
    cache_key = obra_cliente_key(user.team.id, obra_id)
    cached = await redis.get(cache_key)
    if cached:
        return ObraClienteResponse.model_validate_json(cached)

    try:
        obra = await svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    # Ambas as queries são independentes — executadas sequencialmente para evitar
    # conflito de sessão, mas cada uma é uma única query sem N+1.
    items = await item_svc.list_items(obra_id)
    images = await image_svc.list_by_obra(obra_id)

    response = ObraClienteResponse(
        id=obra.id,
        title=obra.title,
        description=obra.description,
        status=obra.status,
        data_entrega=obra.data_entrega,
        items=[ItemClienteView(id=i.id, title=i.title, status=i.status) for i in items],
        images=[ImageClienteView(id=img.id, file_name=img.file_name, file_path=img.file_path)
                for img in images],
    )
    await redis.set(cache_key, response.model_dump_json(), ex=600)
    return response
