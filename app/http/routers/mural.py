import json
from fastapi import APIRouter, HTTPException, Request
from uuid import UUID

from app.http.schemas.obras import (
    CreateMuralPostRequest,
    MuralPostResponse,
    MuralAttachmentResponse,
    RegisterMuralAttachmentRequest,
)
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import ManagerUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import MuralServiceDep, ObraServiceDep
from app.application.dtos.obra import CreateMuralPost, CreateMuralAttachment
from app.domain.entities.user import Roles
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import (
    mural_list_key,
    mural_pattern,
    mural_post_attachments_key,
    mural_obra_attachments_key,
)
from app.core.limiter import limiter

router = APIRouter(prefix="/obras/{obra_id}/mural", tags=["Mural"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _attachment_to_response(a) -> MuralAttachmentResponse:
    return MuralAttachmentResponse(
        id=a.id,
        post_id=a.post_id,
        file_path=a.file_path,
        file_name=a.file_name,
        content_type=a.content_type,
        created_at=a.created_at,
    )


def _post_to_response(post) -> MuralPostResponse:
    return MuralPostResponse(
        id=post.id,
        obra_id=post.obra_id,
        author_id=post.author_id,
        author_nome=post.author_nome,
        content=post.content,
        mentions=post.mentions,
        attachments=[_attachment_to_response(a) for a in post.attachments],
        created_at=post.created_at,
    )


async def _invalidate_mural_cache(redis, team_id: UUID, obra_id: UUID) -> None:
    pattern = mural_pattern(team_id, obra_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


async def _get_post_or_404(svc: MuralServiceDep, post_id: UUID, team_id: UUID):
    try:
        return await svc.get_post(post_id, team_id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Post não encontrado")


# ── Posts ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=MuralPostResponse, status_code=201)
@limiter.limit("30/minute")
async def create_post(
    request: Request,
    obra_id: UUID,
    body: CreateMuralPostRequest,
    user: ManagerUser,
    svc: MuralServiceDep,
):
    """
    Cria um post no mural da obra.
    Restrito a ADMIN, ENGENHEIRO e FINANCEIRO.
    Rate limit: 30 posts/min por IP.
    """
    dto = CreateMuralPost(
        obra_id=obra_id,
        team_id=user.team.id,
        author_id=user.id,
        content=body.content,
        mentions=body.mentions or [],
    )
    try:
        post = await svc.create_post(dto)
    except DomainError as e:
        # "Obra não encontrada" → 404; erros de validação de conteúdo → 422
        if "não encontrada" in e.detail.lower() or "not found" in e.detail.lower():
            raise HTTPException(status_code=404, detail=e.detail)
        raise HTTPException(status_code=422, detail=e.detail)

    redis = get_redis()
    await _invalidate_mural_cache(redis, user.team.id, obra_id)
    return _post_to_response(post)


@router.get("", response_model=PaginatedResponse[MuralPostResponse])
async def list_posts(
    obra_id: UUID,
    user: ManagerUser,
    pagination: Pagination,
    svc: MuralServiceDep,
    obra_svc: ObraServiceDep,
):
    """
    Lista posts do mural (paginado, mais recentes primeiro).
    Cache Redis 5min por tenant+obra+página.
    """
    # Valida que a obra existe e pertence ao time antes de tentar o cache
    try:
        await obra_svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra não encontrada")

    redis = get_redis()
    cache_key = mural_list_key(user.team.id, obra_id, pagination.page, pagination.limit)
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[MuralPostResponse].model_validate_json(cached)

    posts = await svc.list_posts(obra_id, pagination.page, pagination.limit)
    total = await svc.count_posts(obra_id)
    items = [_post_to_response(p) for p in posts]
    result = PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(
    obra_id: UUID,
    post_id: UUID,
    user: ManagerUser,
    svc: MuralServiceDep,
):
    """
    Remove um post do mural.
    ADMIN pode remover qualquer post; demais roles apenas os próprios.
    """
    post = await _get_post_or_404(svc, post_id, user.team.id)

    is_admin = user.role == Roles.ADMIN
    try:
        await svc.delete_post(post, requester_id=user.id, is_admin=is_admin)
    except DomainError as e:
        raise HTTPException(status_code=403, detail=str(e))

    redis = get_redis()
    await _invalidate_mural_cache(redis, user.team.id, obra_id)
    return MessageResponse(message="Post removido com sucesso")


# ── Attachments de Post ───────────────────────────────────────────────────────

@router.post("/{post_id}/attachments", response_model=MuralAttachmentResponse, status_code=201)
@limiter.limit("30/minute")
async def add_attachment(
    request: Request,
    obra_id: UUID,
    post_id: UUID,
    body: RegisterMuralAttachmentRequest,
    user: ManagerUser,
    svc: MuralServiceDep,
):
    """
    Registra um attachment em um post do mural após upload via Supabase.
    O frontend deve primeiro obter a URL de upload via POST /storage/upload-url
    com resource_type='mural' e resource_id={post_id}, fazer o upload direto,
    e então chamar este endpoint para persistir o attachment.
    Rate limit: 30/min por IP.
    """
    post = await _get_post_or_404(svc, post_id, user.team.id)

    # Garante que quem está adicionando o attachment é membro do time correto
    if post.team_id != user.team.id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    dto = CreateMuralAttachment(
        post_id=post_id,
        team_id=user.team.id,
        file_path=body.file_path,
        file_name=body.file_name,
        content_type=body.content_type,
    )
    attachment = await svc.add_attachment(dto)
    # Invalida cache do mural para que o novo attachment apareça nas listagens
    redis = get_redis()
    await _invalidate_mural_cache(redis, user.team.id, obra_id)
    return _attachment_to_response(attachment)


@router.get("/attachments", response_model=list[MuralAttachmentResponse])
async def list_obra_attachments(
    obra_id: UUID,
    user: ManagerUser,
    svc: MuralServiceDep,
    obra_svc: ObraServiceDep,
):
    """Lista somente os attachments presentes no mural da obra. Cache Redis 10min."""
    try:
        await obra_svc.get_obra(obra_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Obra nÃ£o encontrada")

    redis = get_redis()
    cache_key = mural_obra_attachments_key(user.team.id, obra_id)
    cached = await redis.get(cache_key)
    if cached:
        return [MuralAttachmentResponse.model_validate(a) for a in json.loads(cached)]

    attachments = await svc.list_attachments_by_obra(obra_id, user.team.id)
    result = [_attachment_to_response(a) for a in attachments]
    await redis.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in result]),
        ex=600,
    )
    return result


@router.get("/{post_id}/attachments", response_model=list[MuralAttachmentResponse])
async def list_attachments(
    obra_id: UUID,
    post_id: UUID,
    user: ManagerUser,
    svc: MuralServiceDep,
):
    """Lista os attachments de um post do mural. Cache Redis 10min."""
    await _get_post_or_404(svc, post_id, user.team.id)

    redis = get_redis()
    cache_key = mural_post_attachments_key(user.team.id, obra_id, post_id)
    cached = await redis.get(cache_key)
    if cached:
        return [MuralAttachmentResponse.model_validate(a) for a in json.loads(cached)]

    attachments = await svc.list_attachments(post_id)
    result = [_attachment_to_response(a) for a in attachments]
    await redis.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in result]),
        ex=600,
    )
    return result


@router.delete("/{post_id}/attachments/{attachment_id}", response_model=MessageResponse)
async def delete_attachment(
    obra_id: UUID,
    post_id: UUID,
    attachment_id: UUID,
    user: ManagerUser,
    svc: MuralServiceDep,
):
    """
    Remove um attachment de um post.
    ADMIN pode remover qualquer attachment; demais roles apenas dos seus posts.
    """
    post = await _get_post_or_404(svc, post_id, user.team.id)
    try:
        attachment = await svc.get_attachment(attachment_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Attachment não encontrado")

    is_admin = user.role == Roles.ADMIN
    try:
        await svc.delete_attachment(
            attachment, post, requester_id=user.id, is_admin=is_admin
        )
    except DomainError as e:
        raise HTTPException(status_code=403, detail=str(e))

    redis = get_redis()
    await _invalidate_mural_cache(redis, user.team.id, obra_id)
    return MessageResponse(message="Attachment removido com sucesso")
