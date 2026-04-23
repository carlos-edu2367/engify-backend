import json
from fastapi import APIRouter, HTTPException, Request
from uuid import UUID

from app.http.schemas.financeiro import (
    CreateMovimentacaoRequest, MovimentacaoResponse,
    CreatePagamentoRequest, UpdatePagamentoRequest, PagamentoReadResponse, PagamentoResponse,
    CreateMovimentacaoAttachmentRequest, MovimentacaoAttachmentResponse,
    BaixaLoteRequest, BaixaLoteResponse,
)
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import FinanceiroUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import FinanceiroServiceDep
from app.application.dtos.financeiro import (
    CreateMovimentacaoDTO, CreatePagamentoDTO, EditPagamentoDTO,
    AddMovimentacaoAttachmentDTO, BaixaLoteDTO,
)
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import (
    movimentacoes_list_key, movimentacoes_pattern,
    pagamentos_list_key, pagamentos_pattern,
    movimentacao_attachments_key, movimentacao_attachments_pattern,
    movimentacao_delete_lock_key, movimentacao_deleted_tombstone_key,
)
from app.core.limiter import limiter

router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


async def _invalidate_movimentacoes_cache(redis, team_id: UUID) -> None:
    pattern = movimentacoes_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


async def _invalidate_mov_attachments_cache(redis, team_id: UUID, mov_id: UUID) -> None:
    pattern = movimentacao_attachments_pattern(team_id, mov_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


async def _invalidate_pagamentos_cache(redis, team_id: UUID) -> None:
    pattern = pagamentos_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


# ── Movimentações ─────────────────────────────────────────────────────────────

@router.post("/movimentacoes", response_model=MovimentacaoResponse, status_code=201)
@limiter.limit("30/minute")
async def create_movimentacao(
    request: Request,
    body: CreateMovimentacaoRequest,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """Registra uma movimentação financeira manual. Restrito a ADMIN e FIN."""
    dto = CreateMovimentacaoDTO(
        title=body.title,
        type=body.type,
        valor=body.valor,
        classe=body.classe,
        obra_id=body.obra_id,
    )
    mov = await svc.create_movimentacao(dto, user.team.id)
    redis = get_redis()
    await _invalidate_movimentacoes_cache(redis, user.team.id)
    return MovimentacaoResponse(
        id=mov.id, title=mov.title, type=mov.type,
        valor=mov.valor.amount, classe=mov.classe,
        natureza=mov.natureza, obra_id=mov.obra_id,
        pagamento_id=mov.pagamento_id,
        data_movimentacao=mov.data_movimentacao,
    )


@router.delete("/movimentacoes/{movimentacao_id}", response_model=MessageResponse)
@limiter.limit("30/minute")
async def delete_movimentacao(
    request: Request,
    movimentacao_id: UUID,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    redis = get_redis()
    tombstone_key = movimentacao_deleted_tombstone_key(user.team.id, movimentacao_id)
    if await redis.get(tombstone_key):
        return MessageResponse(message="MovimentaÃ§Ã£o removida com sucesso")

    lock_key = movimentacao_delete_lock_key(user.team.id, movimentacao_id)
    lock_acquired = await redis.set(lock_key, "1", ex=30, nx=True)
    if not lock_acquired:
        raise HTTPException(status_code=409, detail="RemoÃ§Ã£o da movimentaÃ§Ã£o jÃ¡ estÃ¡ em processamento")

    try:
        try:
            mov = await svc.get_movimentacao_by_team(movimentacao_id, user.team.id)
        except DomainError:
            if await redis.get(tombstone_key):
                return MessageResponse(message="MovimentaÃ§Ã£o removida com sucesso")
            raise HTTPException(status_code=404, detail="MovimentaÃ§Ã£o nÃ£o encontrada")

        try:
            await svc.delete_movimentacao(mov)
        except DomainError as e:
            raise HTTPException(status_code=400, detail=str(e))

        await redis.set(tombstone_key, "1", ex=60)
        await _invalidate_movimentacoes_cache(redis, user.team.id)
        await _invalidate_mov_attachments_cache(redis, user.team.id, movimentacao_id)
        return MessageResponse(message="MovimentaÃ§Ã£o removida com sucesso")
    finally:
        await redis.delete(lock_key)


from app.http.dependencies.financeiro_filters import MovimentacaoFiltersDep, PagamentoFiltersDep

@router.get("/movimentacoes", response_model=PaginatedResponse[MovimentacaoResponse])
async def list_movimentacoes(
    user: FinanceiroUser,
    pagination: Pagination,
    filters: MovimentacaoFiltersDep,
    svc: FinanceiroServiceDep,
):
    """Lista movimentações do time (paginado). Cache Redis 5min. Restrito a ADMIN e FIN."""
    redis = get_redis()
    filters_dict = filters.model_dump(exclude_none=True)
    cache_key = movimentacoes_list_key(user.team.id, pagination.page, pagination.limit, filters_dict)
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[MovimentacaoResponse].model_validate_json(cached)

    items = await svc.list_movimentacoes(user.team.id, pagination.page, pagination.limit, filters)
    total = await svc.count_movimentacoes(user.team.id, filters)
    result = PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


# ── Movimentações Anexos ───────────────────────────────────────────────────────

@router.post("/movimentacoes/{movimentacao_id}/attachments", response_model=MovimentacaoAttachmentResponse, status_code=201)
async def add_movimentacao_attachment(
    movimentacao_id: UUID,
    body: CreateMovimentacaoAttachmentRequest,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    try:
        mov = await svc.get_movimentacao_by_team(movimentacao_id, user.team.id)
        dto = AddMovimentacaoAttachmentDTO(
            file_path=body.file_path, file_name=body.file_name, content_type=body.content_type
        )
        att = await svc.add_attachment(mov, dto)
        redis = get_redis()
        await _invalidate_mov_attachments_cache(redis, user.team.id, movimentacao_id)
        return MovimentacaoAttachmentResponse(
            id=att.id,
            movimentacao_id=att.movimentacao_id,
            file_path=att.file_path,
            file_name=att.file_name,
            content_type=att.content_type,
            created_at=att.created_at,
        )
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/movimentacoes/{movimentacao_id}/attachments", response_model=list[MovimentacaoAttachmentResponse])
async def list_movimentacao_attachments(
    movimentacao_id: UUID,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """Lista anexos de uma movimentação. Cache Redis 10min."""
    redis = get_redis()
    cache_key = movimentacao_attachments_key(user.team.id, movimentacao_id)
    cached = await redis.get(cache_key)
    if cached:
        return [MovimentacaoAttachmentResponse.model_validate(a) for a in json.loads(cached)]

    try:
        await svc.get_movimentacao_by_team(movimentacao_id, user.team.id)
        atts = await svc.get_attachments(movimentacao_id)
        result = [
            MovimentacaoAttachmentResponse(
                id=a.id, movimentacao_id=a.movimentacao_id,
                file_path=a.file_path, file_name=a.file_name,
                content_type=a.content_type, created_at=a.created_at
            ) for a in atts
        ]
        await redis.set(
            cache_key,
            json.dumps([r.model_dump(mode="json") for r in result]),
            ex=600,
        )
        return result
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/movimentacoes/{movimentacao_id}/attachments/{attachment_id}")
async def delete_movimentacao_attachment(
    movimentacao_id: UUID,
    attachment_id: UUID,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    try:
        await svc.get_movimentacao_by_team(movimentacao_id, user.team.id)
        await svc.delete_attachment(attachment_id, user.team.id)
        redis = get_redis()
        await _invalidate_mov_attachments_cache(redis, user.team.id, movimentacao_id)
        return MessageResponse(message="Anexo removido com sucesso")
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Pagamentos Agendados ───────────────────────────────────────────────────────

@router.post("/pagamentos", response_model=PagamentoResponse, status_code=201)
async def create_pagamento(
    body: CreatePagamentoRequest,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """Agenda um pagamento. Restrito a ADMIN e FIN."""
    dto = CreatePagamentoDTO(
        title=body.title,
        details=body.details,
        valor=body.valor,
        classe=body.classe,
        data_agendada=body.data_agendada,
        payment_cod=body.payment_cod,
        obra_id=body.obra_id,
        diarist_id=body.diarist_id,
    )
    pag = await svc.create_pagamento(dto, user.team.id)
    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    return _pag_response(pag)


@router.get("/pagamentos", response_model=PaginatedResponse[PagamentoReadResponse])
async def list_pagamentos(
    user: FinanceiroUser,
    pagination: Pagination,
    filters: PagamentoFiltersDep,
    svc: FinanceiroServiceDep,
):
    """Lista pagamentos agendados (paginado). Cache Redis 5min. Restrito a ADMIN e FIN."""
    redis = get_redis()
    filters_dict = filters.model_dump(exclude_none=True)
    cache_key = pagamentos_list_key(user.team.id, pagination.page, pagination.limit, filters_dict)
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[PagamentoReadResponse].model_validate_json(cached)

    items = await svc.list_pagamentos(user.team.id, pagination.page, pagination.limit, filters)
    total = await svc.count_pagamentos(user.team.id, filters)
    result = PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


@router.get("/pagamentos/{pagamento_id}", response_model=PagamentoReadResponse)
async def get_pagamento(
    pagamento_id: UUID,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """Retorna um pagamento agendado pelo ID. Restrito a ADMIN e FIN."""
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return _pag_read_response(pag)


@router.put("/pagamentos/{pagamento_id}", response_model=PagamentoResponse)
async def update_pagamento(
    pagamento_id: UUID,
    body: UpdatePagamentoRequest,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """Edita um pagamento agendado. Restrito a ADMIN e FIN."""
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    dto = EditPagamentoDTO(
        title=body.title,
        details=body.details,
        valor=body.valor,
        data_agendada=body.data_agendada,
        payment_cod=body.payment_cod,
        obra_id=body.obra_id,
    )
    try:
        updated = await svc.edit_pagamento(pag, dto)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    return _pag_response(updated)


@router.patch("/pagamentos/{pagamento_id}/pay", response_model=MovimentacaoResponse)
async def pay_pagamento(
    pagamento_id: UUID,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """
    Marca pagamento como pago e cria Movimentação de saída automaticamente.
    Restrito a ADMIN e FIN.
    """
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    try:
        mov = await svc.pay_pagamento(pag)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    await _invalidate_movimentacoes_cache(redis, user.team.id)
    return MovimentacaoResponse(
        id=mov.id, title=mov.title, type=mov.type,
        valor=mov.valor.amount, classe=mov.classe,
        natureza=mov.natureza, obra_id=mov.obra_id,
        pagamento_id=mov.pagamento_id,
        data_movimentacao=mov.data_movimentacao,
    )


@router.post("/pagamentos/baixa-lote", response_model=BaixaLoteResponse, status_code=200)
async def baixa_lote_pagamentos(
    body: BaixaLoteRequest,
    user: FinanceiroUser,
    svc: FinanceiroServiceDep,
):
    """
    Baixa em lote: marca múltiplos pagamentos como pagos e gera uma única
    movimentação financeira consolidada. Operação atômica.
    Restrito a ADMIN e FIN.
    """
    if not body.pagamento_ids:
        raise HTTPException(status_code=422, detail="A lista de pagamentos não pode ser vazia")

    dto = BaixaLoteDTO(
        pagamento_ids=body.pagamento_ids,
        team_id=user.team.id,
    )
    try:
        resultado = await svc.pay_lote(dto)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    await _invalidate_movimentacoes_cache(redis, user.team.id)

    return BaixaLoteResponse(
        quantidade=resultado.quantidade,
        valor_total=resultado.valor_total,
        movimentacao_id=resultado.movimentacao_id,
    )


def _pag_response(p) -> PagamentoResponse:
    return PagamentoResponse(
        id=p.id, title=p.title, details=p.details,
        valor=p.valor.amount, classe=p.classe, status=p.status,
        data_agendada=p.data_agendada, payment_cod=p.payment_cod,
        obra_id=p.obra_id, diarist_id=p.diarist_id,
        payment_date=p.payment_date,
    )


def _pag_read_response(p) -> PagamentoReadResponse:
    return PagamentoReadResponse(
        id=p.id, title=p.title, details=p.details,
        valor=p.valor.amount, classe=p.classe, status=p.status,
        data_agendada=p.data_agendada, payment_cod=p.payment_cod,
        pix_copy_and_past=p.pix_copy_and_past,
        obra_id=p.obra_id, diarist_id=p.diarist_id,
        payment_date=p.payment_date,
    )
