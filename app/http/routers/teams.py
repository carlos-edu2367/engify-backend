import json
from fastapi import APIRouter, HTTPException, Request
from uuid import UUID

from app.http.schemas.teams import (
    CreateTeamRequest, CreateFirstUserRequest, UpdateTeamRequest,
    TeamResponse, TeamCreatedResponse, ExpirationResponse,
    InviteUserRequest, InviteResponse,
    CreateDiaristRequest, UpdateDiaristRequest, DiaristResponse,
)
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import CurrentUser, AdminUser, ManagerUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import TeamServiceDep, DiaristServiceDep, UserServiceDep
from app.application.dtos.team import CreateTeam, CreateFirstUser, CreateDiarist, EditDiarist
from app.application.dtos.user import CreateSolicitacaoRegistro
from app.infra.cache.client import get_redis
from app.infra.cache.keys import team_key, diaristas_list_key, diaristas_pattern
from app.core.limiter import limiter
from app.domain.errors import DomainError

router = APIRouter(prefix="/teams", tags=["Times"])


# ── Time ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=TeamCreatedResponse, status_code=201)
@limiter.limit("5/minute")
async def create_team(request: Request, body: CreateTeamRequest, svc: TeamServiceDep):
    """
    Cria um novo time (tenant). Rota pública — sem autenticação.
    Retorna a `key` one-time para criação do primeiro admin.
    A key é exibida apenas uma vez e não pode ser recuperada depois.
    """
    try:
        dto = CreateTeam(title=body.title, cnpj=body.cnpj)
        team = await svc.create_team(dto)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TeamCreatedResponse(
        id=team.id,
        title=team.title,
        cnpj=team.cnpj,
        plan=team.plan,
        key=team.key,
    )


@router.post("/first-user", status_code=201)
@limiter.limit("5/minute")
async def create_first_user(request: Request, body: CreateFirstUserRequest, svc: TeamServiceDep):
    """
    Cria o primeiro usuário (ADMIN) do time usando a key one-time.
    Rota pública — sem autenticação.
    """
    try:
        dto = CreateFirstUser(
            nome=body.nome, email=body.email, senha=body.senha,
            cpf=body.cpf, cnpj=body.cnpj, key=body.key,
        )
        user = await svc.create_first_user(dto)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Invalida cache do time (key foi consumida — estado do time mudou)
    redis = get_redis()
    await redis.delete(team_key(user.team.id))
    return {"message": "Administrador criado com sucesso", "user_id": str(user.id)}


@router.get("/me", response_model=TeamResponse)
async def get_my_team(user: CurrentUser, svc: TeamServiceDep):
    """Retorna os dados do time do usuário autenticado. Cache Redis 5min."""
    redis = get_redis()
    cache_key = team_key(user.team.id)
    cached = await redis.get(cache_key)
    if cached:
        return TeamResponse.model_validate_json(cached)

    days = await svc.get_days_for_expire(user.team.id)
    response = TeamResponse(
        id=user.team.id,
        title=user.team.title,
        cnpj=user.team.cnpj,
        plan=user.team.plan,
        days_to_expire=days,
    )
    await redis.set(cache_key, response.model_dump_json(), ex=300)
    return response


@router.put("/me", response_model=TeamResponse)
async def update_team(body: UpdateTeamRequest, user: AdminUser, svc: TeamServiceDep):
    """Atualiza o nome do time. Restrito a ADMIN."""
    if not body.title:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar")

    saved = await svc.update_team(user.team, body.title)
    days = saved.get_days_for_expire()

    # Invalida cache do time
    redis = get_redis()
    await redis.delete(team_key(saved.id))

    return TeamResponse(
        id=saved.id, title=saved.title,
        cnpj=saved.cnpj, plan=saved.plan, days_to_expire=days,
    )


@router.get("/me/expiration", response_model=ExpirationResponse)
async def get_expiration(user: CurrentUser, svc: TeamServiceDep):
    """Dias até o plano expirar."""
    days = await svc.get_days_for_expire(user.team.id)
    return ExpirationResponse(days_to_expire=days)


@router.post("/me/invite", response_model=InviteResponse, status_code=201)
async def invite_user(body: InviteUserRequest, user: AdminUser, svc: UserServiceDep):
    """
    Convida um usuário para o time via e-mail.
    Gera um SolicitacaoCadastro que expira em 7 dias.
    Restrito a ADMIN.
    """
    dto = CreateSolicitacaoRegistro(email=body.email, role=body.role)
    invite = await svc.invite_user(dto, user)
    return InviteResponse(id=invite.id, email=invite.email, role=invite.role)


# ── Diaristas ────────────────────────────────────────────────────────────────

@router.post("/me/diaristas", response_model=DiaristResponse, status_code=201)
async def create_diarist(body: CreateDiaristRequest, user: AdminUser, svc: DiaristServiceDep):
    """Cria um diarista no time. Restrito a ADMIN."""
    dto = CreateDiarist(
        nome=body.nome, descricao=body.descricao,
        valor_diaria=body.valor_diaria, chave_pix=body.chave_pix,
    )
    diarist = await svc.create_diarist(dto, user.team.id)
    # Invalida cache de listagem do time
    redis = get_redis()
    await _invalidate_diaristas_cache(redis, user.team.id)
    return DiaristResponse(
        id=diarist.id, nome=diarist.nome, descricao=diarist.descricao,
        valor_diaria=diarist.valor_diaria.amount, chave_pix=diarist.chave_pix,
    )


@router.get("/me/diaristas", response_model=PaginatedResponse[DiaristResponse])
async def list_diaristas(user: ManagerUser, pagination: Pagination, svc: DiaristServiceDep):
    """Lista diaristas do time (paginado). Cache Redis 10min."""
    redis = get_redis()
    cache_key = diaristas_list_key(user.team.id, pagination.page, pagination.limit)

    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[DiaristResponse].model_validate_json(cached)

    diarists, total = await svc.list_diarists_paginated(
        user.team.id, pagination.limit, pagination.page
    )
    items = [
        DiaristResponse(
            id=d.id, nome=d.nome, descricao=d.descricao,
            valor_diaria=d.valor_diaria.amount, chave_pix=d.chave_pix,
        )
        for d in diarists
    ]
    result = PaginatedResponse.build(items=items, page=pagination.page,
                                     limit=pagination.limit, total=total)
    await redis.set(cache_key, result.model_dump_json(), ex=600)
    return result


@router.put("/me/diaristas/{diarist_id}", response_model=DiaristResponse)
async def update_diarist(
    diarist_id: UUID, body: UpdateDiaristRequest,
    user: AdminUser, svc: DiaristServiceDep,
):
    """Edita um diarista. Restrito a ADMIN."""
    try:
        diarist = await svc.get_diarist(diarist_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Diarista não encontrado")

    dto = EditDiarist(
        nome=body.nome, descricao=body.descricao,
        valor_diaria=body.valor_diaria, chave_pix=body.chave_pix,
    )
    updated = await svc.edit_diarist(diarist, dto)
    redis = get_redis()
    await _invalidate_diaristas_cache(redis, user.team.id)
    return DiaristResponse(
        id=updated.id, nome=updated.nome, descricao=updated.descricao,
        valor_diaria=updated.valor_diaria.amount, chave_pix=updated.chave_pix,
    )


@router.delete("/me/diaristas/{diarist_id}", response_model=MessageResponse)
async def delete_diarist(diarist_id: UUID, user: AdminUser, svc: DiaristServiceDep):
    """Soft-delete de diarista. Restrito a ADMIN."""
    try:
        diarist = await svc.get_diarist(diarist_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Diarista não encontrado")

    await svc.delete_diarist(diarist)
    redis = get_redis()
    await _invalidate_diaristas_cache(redis, user.team.id)
    return MessageResponse(message="Diarista removido com sucesso")


async def _invalidate_diaristas_cache(redis, team_id: UUID) -> None:
    pattern = diaristas_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)
