from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.http.schemas.obra_financeiro import ObraFinanceiroResumoResponse
from app.http.dependencies.auth import FinanceiroUser
from app.http.dependencies.services import ObraFinanceiroResumoServiceDep
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import obra_financeiro_resumo_key

router = APIRouter(prefix="/obras", tags=["Financeiro"])


@router.get("/{obra_id}/financeiro/resumo", response_model=ObraFinanceiroResumoResponse)
async def get_obra_financeiro_resumo(
    obra_id: UUID,
    user: FinanceiroUser,
    svc: ObraFinanceiroResumoServiceDep,
):
    """
    Retorna o resumo financeiro consolidado de uma obra: entradas, saídas,
    comprometido, margem projetada e custo por classe. Cache Redis 5min.
    Restrito a ADMIN e FINANCEIRO.
    """
    redis = get_redis()
    cache_key = obra_financeiro_resumo_key(user.team.id, obra_id)
    cached = await redis.get(cache_key)
    if cached:
        return ObraFinanceiroResumoResponse.model_validate_json(cached)

    try:
        result = await svc.get_resumo(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result
