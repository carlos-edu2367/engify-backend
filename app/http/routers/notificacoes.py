from fastapi import APIRouter
from uuid import UUID

from app.http.schemas.notificacao import (
    NotificacaoResponse, NotificacaoListResponse, ContagemNaoLidasResponse,
)
from app.http.schemas.common import MessageResponse
from app.http.dependencies.auth import CurrentUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import NotificacaoServiceDep
from app.infra.cache.client import get_redis
from app.infra.cache.keys import notif_list_key, notif_count_key, notif_pattern

import json

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])

_TTL = 60


@router.get("", response_model=NotificacaoListResponse)
async def list_notificacoes(
    user: CurrentUser,
    svc: NotificacaoServiceDep,
    pagination: Pagination,
):
    redis = await get_redis()
    page, limit = pagination.page, pagination.limit

    cache_key = notif_list_key(user.id, user.team.id, page, limit)
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return NotificacaoListResponse(**json.loads(cached))

    items = await svc.list_notificacoes(user.id, user.team.id, page, limit)
    total = await svc.count_notificacoes(user.id, user.team.id)

    response = NotificacaoListResponse(
        items=[
            NotificacaoResponse(
                id=n.id,
                tipo=n.tipo,
                titulo=n.titulo,
                mensagem=n.mensagem,
                reference_id=n.reference_id,
                lida=n.lida,
                created_at=n.created_at,
            )
            for n in items
        ],
        total=total,
        page=page,
        limit=limit,
    )

    if redis:
        await redis.setex(cache_key, _TTL, response.model_dump_json())

    return response


@router.get("/contagem", response_model=ContagemNaoLidasResponse)
async def contagem_nao_lidas(
    user: CurrentUser,
    svc: NotificacaoServiceDep,
):
    redis = await get_redis()
    cache_key = notif_count_key(user.id, user.team.id)

    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return ContagemNaoLidasResponse(nao_lidas=int(cached))

    count = await svc.count_nao_lidas(user.id, user.team.id)

    if redis:
        await redis.setex(cache_key, _TTL, str(count))

    return ContagemNaoLidasResponse(nao_lidas=count)


@router.patch("/{notif_id}/lida", response_model=NotificacaoResponse)
async def marcar_lida(
    notif_id: UUID,
    user: CurrentUser,
    svc: NotificacaoServiceDep,
):
    notif = await svc.marcar_lida(notif_id, user.id, user.team.id)
    await _invalidate_cache(user.id, user.team.id)
    return NotificacaoResponse(
        id=notif.id,
        tipo=notif.tipo,
        titulo=notif.titulo,
        mensagem=notif.mensagem,
        reference_id=notif.reference_id,
        lida=notif.lida,
        created_at=notif.created_at,
    )


@router.patch("/marcar-todas-lidas", response_model=MessageResponse)
async def marcar_todas_lidas(
    user: CurrentUser,
    svc: NotificacaoServiceDep,
):
    await svc.marcar_todas_lidas(user.id, user.team.id)
    await _invalidate_cache(user.id, user.team.id)
    return MessageResponse(message="Todas as notificações foram marcadas como lidas")


async def _invalidate_cache(user_id: UUID, team_id: UUID) -> None:
    redis = await get_redis()
    if not redis:
        return
    pattern = notif_pattern(user_id, team_id)
    async for key in redis.scan_iter(pattern):
        await redis.delete(key)
