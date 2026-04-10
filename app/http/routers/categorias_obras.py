from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.http.schemas.obras import (
    CreateCategoriaObraRequest, UpdateCategoriaObraRequest,
    CategoriaObraResponse, CategoriaObraListItem, ObraListItem,
)
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import CurrentUser, EngineerUser, AdminUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import CategoriaObraServiceDep
from app.application.dtos.obra import CreateCategoriaObraDTO, UpdateCategoriaObraDTO
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import (
    categorias_obra_list_key, categoria_obra_detail_key, categorias_obra_pattern,
)

router = APIRouter(prefix="/categorias-obra", tags=["Categorias de Obra"])


def _categoria_to_response(cat) -> CategoriaObraResponse:
    return CategoriaObraResponse(
        id=cat.id,
        team_id=cat.team_id,
        title=cat.title,
        descricao=cat.descricao,
        cor=cat.cor,
        created_at=cat.created_at,
    )


def _categoria_to_list_item(cat) -> CategoriaObraListItem:
    return CategoriaObraListItem(
        id=cat.id,
        title=cat.title,
        descricao=cat.descricao,
        cor=cat.cor,
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
        categoria_id=obra.categoria_id,
    )


async def _invalidate_categorias_cache(redis, team_id: UUID) -> None:
    pattern = categorias_obra_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=CategoriaObraResponse, status_code=201)
async def create_categoria(
    body: CreateCategoriaObraRequest,
    user: EngineerUser,
    svc: CategoriaObraServiceDep,
):
    """Cria uma nova categoria de obra. Restrito a ADMIN e ENG."""
    dto = CreateCategoriaObraDTO(
        title=body.title,
        team_id=user.team.id,
        descricao=body.descricao,
        cor=body.cor,
    )
    try:
        categoria = await svc.create_categoria(dto)
    except DomainError as e:
        raise HTTPException(status_code=409, detail=str(e))
    redis = get_redis()
    await _invalidate_categorias_cache(redis, user.team.id)
    return _categoria_to_response(categoria)


@router.get("", response_model=PaginatedResponse[CategoriaObraListItem])
async def list_categorias(
    user: CurrentUser,
    pagination: Pagination,
    svc: CategoriaObraServiceDep,
):
    """Lista categorias do time (paginado, ordenado por nome). Cache Redis 5min."""
    redis = get_redis()
    cache_key = categorias_obra_list_key(user.team.id, pagination.page, pagination.limit)
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[CategoriaObraListItem].model_validate_json(cached)

    categorias = await svc.list_categorias(user.team.id, pagination.page, pagination.limit)
    total = await svc.count_categorias(user.team.id)

    items = [_categoria_to_list_item(c) for c in categorias]
    result = PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


@router.get("/{categoria_id}", response_model=CategoriaObraResponse)
async def get_categoria(
    categoria_id: UUID,
    user: CurrentUser,
    svc: CategoriaObraServiceDep,
):
    """Retorna detalhes de uma categoria. Cache Redis 5min."""
    redis = get_redis()
    cache_key = categoria_obra_detail_key(user.team.id, categoria_id)
    cached = await redis.get(cache_key)
    if cached:
        return CategoriaObraResponse.model_validate_json(cached)

    try:
        categoria = await svc.get_categoria(categoria_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    response = _categoria_to_response(categoria)
    await redis.set(cache_key, response.model_dump_json(), ex=300)
    return response


@router.patch("/{categoria_id}", response_model=CategoriaObraResponse)
async def update_categoria(
    categoria_id: UUID,
    body: UpdateCategoriaObraRequest,
    user: EngineerUser,
    svc: CategoriaObraServiceDep,
):
    """Atualiza dados da categoria. Restrito a ADMIN e ENG."""
    if not any([body.title, body.descricao is not None, body.cor is not None]):
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar")

    try:
        categoria = await svc.get_categoria(categoria_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    dto = UpdateCategoriaObraDTO(
        title=body.title,
        descricao=body.descricao,
        cor=body.cor,
    )
    try:
        updated = await svc.update_categoria(categoria, dto)
    except DomainError as e:
        raise HTTPException(status_code=409, detail=str(e))

    redis = get_redis()
    await _invalidate_categorias_cache(redis, user.team.id)
    return _categoria_to_response(updated)


@router.delete("/{categoria_id}", response_model=MessageResponse)
async def delete_categoria(
    categoria_id: UUID,
    user: AdminUser,
    svc: CategoriaObraServiceDep,
):
    """
    Remove a categoria. As obras vinculadas têm categoria_id definido como null.
    Restrito a ADMIN.
    """
    try:
        categoria = await svc.get_categoria(categoria_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    await svc.delete_categoria(categoria)
    redis = get_redis()
    await _invalidate_categorias_cache(redis, user.team.id)
    return MessageResponse(message="Categoria removida com sucesso")


# ── Obras por categoria ────────────────────────────────────────────────────────

@router.get("/{categoria_id}/obras", response_model=PaginatedResponse[ObraListItem])
async def list_obras_by_categoria(
    categoria_id: UUID,
    user: CurrentUser,
    pagination: Pagination,
    svc: CategoriaObraServiceDep,
):
    """Lista obras de uma categoria (paginado)."""
    try:
        await svc.get_categoria(categoria_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    obras = await svc.list_obras_by_categoria(
        categoria_id, user.team.id, pagination.page, pagination.limit
    )
    total = await svc.count_obras_by_categoria(categoria_id, user.team.id)

    items = [_obra_to_list_item(o) for o in obras]
    return PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
