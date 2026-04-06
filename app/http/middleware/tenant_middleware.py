import json
from uuid import UUID
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.infra.cache.client import get_redis
from app.infra.cache.keys import team_key
from app.infra.db.session import async_session_factory
from app.infra.db.repositories.team_repository import TeamRepositoryImpl
from app.domain.errors import ExpiredPlan
from app.domain.entities.team import Team, Plans
from app.core.config import settings

# TTL de cache para dados do time (plano, expiração)
_TEAM_CACHE_TTL = 300  # 5 minutos


async def _load_team(team_id_str: str) -> Team | None:
    """
    Carrega o time com cache-first:
    1. Tenta Redis (serializado como JSON)
    2. Em caso de miss, busca no banco e armazena no cache
    """
    redis = get_redis()
    cache_key = team_key(UUID(team_id_str))

    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        team = object.__new__(Team)
        team.id = UUID(data["id"])
        team.title = data["title"]
        team.cnpj = data["cnpj"]
        team.plan = Plans(data["plan"])
        from datetime import datetime, timezone
        team.expiration_date = datetime.fromisoformat(data["expiration_date"])
        team.key = data.get("key")
        return team

    # Cache miss — busca no banco
    async with async_session_factory() as session:
        repo = TeamRepositoryImpl(session)
        try:
            team = await repo.get_by_id(UUID(team_id_str))
        except Exception:
            return None

    # Serializa para cache
    payload = json.dumps({
        "id": str(team.id),
        "title": team.title,
        "cnpj": team.cnpj,
        "plan": team.plan.value,
        "expiration_date": team.expiration_date.isoformat(),
        "key": team.key,
    })
    await redis.set(cache_key, payload, ex=_TEAM_CACHE_TTL)
    return team


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Valida o tenant em toda request autenticada:
    1. Extrai team_id do JWT (injetado pelo AuthMiddleware)
    2. Carrega o Team do cache Redis (fallback ao banco)
    3. Verifica se o plano está ativo (ensure_can_operate)
    4. Injeta request.state.team e request.state.team_id

    Rotas públicas (sem jwt_payload) são ignoradas.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        payload = getattr(request.state, "jwt_payload", None)
        if payload is None:
            return await call_next(request)

        team_id_str = payload.get("team_id")
        if not team_id_str:
            return JSONResponse({"detail": "Token mal formado: team_id ausente"}, status_code=401)

        team = await _load_team(team_id_str)
        if team is None:
            return JSONResponse({"detail": "Time não encontrado"}, status_code=404)

        try:
            team.ensure_can_operate()
        except ExpiredPlan:
            return JSONResponse(
                {"detail": "O plano do seu time expirou. Renove para continuar."},
                status_code=403,
            )

        request.state.team = team
        request.state.team_id = team.id

        return await call_next(request)
