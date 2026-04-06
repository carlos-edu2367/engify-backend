from fastapi import APIRouter, HTTPException, Query, Request
from uuid import UUID
from datetime import datetime

from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import EngineerUser, AdminUser, ManagerUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import DiaryServiceDep
from app.application.dtos.obra import CreateDiary, EditDiary, DiariesResponse
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import diarias_list_key, diarias_pattern, pagamentos_pattern
from app.core.limiter import limiter

router = APIRouter(prefix="/diarias", tags=["Diárias"])


def _diary_to_response(d) -> DiariesResponse:
    return DiariesResponse(
        diarist_id=d.diarista.id,
        diarist_name=d.diarista.nome,
        descricao_diaria=d.descricao_diaria,
        obra_id=d.obra.id,
        obra_title=d.obra.title,
        quantidade=d.quantidade,
        data=d.data,
    )


async def _invalidate_diarias_cache(redis, team_id: UUID) -> None:
    pattern = diarias_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


@router.post("", response_model=DiariesResponse, status_code=201)
async def create_diary(body: CreateDiary, user: EngineerUser, svc: DiaryServiceDep):
    """
    Registra uma diária.
    Cria automaticamente uma Movimentação de saída (tipo DIARISTA) na mesma transação.
    Restrito a ADMIN e ENG.
    """
    try:
        diary = await svc.create_diary(body, user.team.id)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redis = get_redis()
    await _invalidate_diarias_cache(redis, user.team.id)
    async for key in redis.scan_iter(match=pagamentos_pattern(user.team.id), count=100):
        await redis.delete(key)
    return _diary_to_response(diary)


@router.get("", response_model=PaginatedResponse[DiariesResponse])
async def list_diaries(
    user: ManagerUser,
    pagination: Pagination,
    svc: DiaryServiceDep,
    start: datetime = Query(..., description="Data inicial (ISO 8601)"),
    end: datetime = Query(..., description="Data final (ISO 8601)"),
):
    """
    Lista diárias por período. Cache Redis 5min.
    Restrito a ADMIN, ENG e FIN.
    """
    if start > end:
        raise HTTPException(status_code=422, detail="Data inicial deve ser anterior à data final")

    redis = get_redis()
    cache_key = diarias_list_key(
        user.team.id,
        start.isoformat(), end.isoformat(),
        pagination.page, pagination.limit,
    )
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[DiariesResponse].model_validate_json(cached)

    diaries = await svc.list_diaries_by_period(
        init_date=start, end_date=end,
        team_id=user.team.id,
        page=pagination.page, limit=pagination.limit,
    )
    total = await svc.count_diaries_by_period(
        init_date=start, end_date=end, team_id=user.team.id
    )
    result = PaginatedResponse.build(
        items=diaries, page=pagination.page,
        limit=pagination.limit, total=total,
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


@router.put("/{diary_id}", response_model=DiariesResponse)
async def update_diary(
    diary_id: UUID, body: EditDiary,
    user: EngineerUser, svc: DiaryServiceDep,
):
    """Edita uma diária. Restrito a ADMIN e ENG."""
    try:
        diary = await svc.get_diary(diary_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Diária não encontrada")

    updated = await svc.edit_diary(body, diary)
    redis = get_redis()
    await _invalidate_diarias_cache(redis, user.team.id)
    return _diary_to_response(updated)


@router.delete("/{diary_id}", response_model=MessageResponse)
async def delete_diary(diary_id: UUID, user: AdminUser, svc: DiaryServiceDep):
    """Soft-delete de diária. Restrito a ADMIN."""
    try:
        diary = await svc.get_diary(diary_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Diária não encontrada")

    await svc.remove_diary(diary)
    redis = get_redis()
    await _invalidate_diarias_cache(redis, user.team.id)
    return MessageResponse(message="Diária removida com sucesso")
