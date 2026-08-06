import json
from typing import Annotated, Literal
from fastapi import APIRouter, HTTPException, Query, Request
from uuid import UUID

from app.http.schemas.financeiro import (
    CreateMovimentacaoRequest, MovimentacaoResponse, PayPagamentoResponse,
    CreatePagamentoRequest, CreatePagamentoParceladoRequest,
    UpdatePagamentoRequest, PagamentoReadResponse, PagamentoResponse,
    CreateMovimentacaoAttachmentRequest, MovimentacaoAttachmentResponse,
    CreatePagamentoAttachmentRequest, PagamentoAttachmentResponse,
    BaixaLoteRequest, BaixaLoteResponse,
    ComprovacaoResponse, ComprovacaoMovimentacaoResponse, ComprovacaoAttachmentResponse,
)
from app.http.schemas.commission_report import (
    CreateCommissionReportRequest,
    CreateCommissionReportResponse,
    CommissionReportJobStatusResponse,
)
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.dependencies.auth import FinanceiroUser, ManagerUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import (
    FinanceiroServiceDep,
    FinanceiroFluxoCaixaServiceDep,
    GenerateCommissionReportUseCaseDep,
    CommissionReportJobStatusUseCaseDep,
)
from app.application.dtos.financeiro import (
    CreateMovimentacaoDTO, CreatePagamentoDTO, CreatePagamentoParceladoDTO, EditPagamentoDTO,
    AddMovimentacaoAttachmentDTO, AddPagamentoAttachmentDTO, BaixaLoteDTO,
)
from app.application.use_cases.generate_monthly_commission_report import (
    GenerateMonthlyCommissionReportInput,
    GetCommissionReportJobStatusInput,
)
from app.domain.errors import DomainError
from app.infra.cache.client import get_redis
from app.infra.cache.keys import (
    movimentacoes_list_key, movimentacoes_pattern,
    pagamentos_list_key, pagamentos_version_key,
    movimentacao_attachments_key, movimentacao_attachments_pattern,
    pagamento_attachments_key, pagamento_attachments_pattern,
    movimentacao_delete_lock_key, movimentacao_deleted_tombstone_key,
    fluxo_caixa_key, fluxo_caixa_pattern, public_obra_key,
)
from app.infra.cache.invalidation import invalidate_obra_financeiro_resumo
from app.core.limiter import limiter

router = APIRouter(prefix="/financeiro", tags=["Financeiro"])


async def _invalidate_movimentacoes_cache(redis, team_id: UUID) -> None:
    pattern = movimentacoes_pattern(team_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)
    await _invalidate_fluxo_caixa_cache(redis, team_id)
    await invalidate_obra_financeiro_resumo(redis, team_id)


async def _invalidate_mov_attachments_cache(redis, team_id: UUID, mov_id: UUID) -> None:
    pattern = movimentacao_attachments_pattern(team_id, mov_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


async def _invalidate_pagamento_attachments_cache(redis, team_id: UUID, pagamento_id: UUID) -> None:
    pattern = pagamento_attachments_pattern(team_id, pagamento_id)
    async for key in redis.scan_iter(match=pattern, count=100):
        await redis.delete(key)


async def _invalidate_pagamentos_cache(redis, team_id: UUID) -> None:
    # Incrementa a versao em vez de fazer SCAN+DEL: uma listagem em andamento
    # que ainda vai escrever no cache usa a versao antiga (lida antes desta
    # invalidacao), entao a escrita cai numa chave orfa que nenhuma leitura
    # futura acessa e que expira sozinha pelo TTL. Isso fecha a race em que
    # a escrita da listagem chega depois do SCAN+DEL e deixa dado stale.
    await redis.incr(pagamentos_version_key(team_id))
    await invalidate_obra_financeiro_resumo(redis, team_id)


async def _invalidate_fluxo_caixa_cache(redis, team_id: UUID) -> None:
    pattern = fluxo_caixa_pattern(team_id)
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


from app.http.dependencies.financeiro_filters import MovimentacaoFiltersDep, PagamentoFiltersDep, PagamentoScopeDep

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


from app.http.schemas.financeiro import FluxoCaixaResponse

@router.get("/fluxo-caixa", response_model=FluxoCaixaResponse)
async def get_fluxo_caixa(
    user: FinanceiroUser,
    svc: FinanceiroFluxoCaixaServiceDep,
    range: str = "6m",
):
    """
    Retorna o fluxo de caixa agregado (entradas vs saídas) por mês.
    Cache Redis 5min.
    """
    if range not in ["6m", "12m", "24m"]:
        range = "6m"

    redis = get_redis()
    cache_key = fluxo_caixa_key(user.team.id, range)
    cached = await redis.get(cache_key)
    if cached:
        return FluxoCaixaResponse.model_validate_json(cached)

    result = await svc.get_fluxo_caixa(user.team.id, range)
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
            file_path=body.file_path, file_name=body.file_name, content_type=body.content_type,
            kind=body.kind,
        )
        att = await svc.add_attachment(mov, dto)
        redis = get_redis()
        await _invalidate_mov_attachments_cache(redis, user.team.id, movimentacao_id)
        if body.kind == "comprovante":
            await _invalidate_pagamentos_cache(redis, user.team.id)
        if mov.obra_id is not None:
            await redis.delete(public_obra_key(mov.obra_id))
        return MovimentacaoAttachmentResponse(
            id=att.id,
            movimentacao_id=att.movimentacao_id,
            file_path=att.file_path,
            file_name=att.file_name,
            content_type=att.content_type,
            created_at=att.created_at,
            kind=att.kind,
            origem_pagamento_id=att.origem_pagamento_id,
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
                content_type=a.content_type, created_at=a.created_at,
                kind=a.kind, origem_pagamento_id=a.origem_pagamento_id,
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
        mov = await svc.get_movimentacao_by_team(movimentacao_id, user.team.id)
        await svc.delete_attachment(attachment_id, user.team.id)
        redis = get_redis()
        await _invalidate_mov_attachments_cache(redis, user.team.id, movimentacao_id)
        if mov.obra_id is not None:
            await redis.delete(public_obra_key(mov.obra_id))
        return MessageResponse(message="Anexo removido com sucesso")
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Pagamentos Agendados ───────────────────────────────────────────────────────

@router.post("/pagamentos", response_model=PagamentoResponse, status_code=201)
async def create_pagamento(
    body: CreatePagamentoRequest,
    user: ManagerUser,
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
        requires_receipt=body.requires_receipt,
    )
    try:
        pag = await svc.create_pagamento(dto, user.team.id, actor_user=user)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    return _pag_response(pag)


@router.post("/pagamentos/parcelado", response_model=list[PagamentoResponse], status_code=201)
async def create_pagamento_parcelado(
    body: CreatePagamentoParceladoRequest,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    """Agenda um pagamento em N parcelas. Restrito a ADMIN, ENG e FIN."""
    dto = CreatePagamentoParceladoDTO(
        title=body.title,
        details=body.details,
        valor=body.valor,
        classe=body.classe,
        data_agendada=body.data_agendada,
        parcelas=body.parcelas,
        payment_cods=body.payment_cods,
        obra_id=body.obra_id,
        diarist_id=body.diarist_id,
        requires_receipt=body.requires_receipt,
    )
    try:
        parcelas = await svc.create_pagamento_parcelado(dto, user.team.id, actor_user=user)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    return [_pag_response(p) for p in parcelas]


@router.get("/pagamentos", response_model=PaginatedResponse[PagamentoReadResponse])
async def list_pagamentos(
    user: ManagerUser,
    pagination: Pagination,
    filters: PagamentoFiltersDep,
    scope: PagamentoScopeDep,
    svc: FinanceiroServiceDep,
):
    """Lista pagamentos agendados (paginado). Cache Redis 5min. Restrito a ADMIN e FIN.

    Engenheiros veem só os próprios pagamentos por padrão (scope=mine);
    scope=all mostra os pagamentos de todos os engenheiros do time.
    """
    redis = get_redis()
    effective_filters = svc.get_pagamento_filters_for_actor(filters, user, scope)
    filters_dict = effective_filters.model_dump(exclude_none=True)
    version_raw = await redis.get(pagamentos_version_key(user.team.id))
    version = int(version_raw) if version_raw else 0
    cache_key = pagamentos_list_key(user.team.id, pagination.page, pagination.limit, version, filters_dict)
    cached = await redis.get(cache_key)
    if cached:
        return PaginatedResponse[PagamentoReadResponse].model_validate_json(cached)

    items = await svc.list_pagamentos(user.team.id, pagination.page, pagination.limit, effective_filters, actor_user=user, scope=scope)
    total = await svc.count_pagamentos(user.team.id, effective_filters, actor_user=user, scope=scope)
    result = PaginatedResponse.build(
        items=items, page=pagination.page, limit=pagination.limit, total=total
    )
    await redis.set(cache_key, result.model_dump_json(), ex=300)
    return result


@router.get("/pagamentos/{pagamento_id}", response_model=PagamentoReadResponse)
async def get_pagamento(
    pagamento_id: UUID,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    """Retorna um pagamento agendado pelo ID. Restrito a ADMIN e FIN."""
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id, actor_user=user)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return _pag_read_response(pag)


@router.get("/pagamentos/{pagamento_id}/comprovacao", response_model=ComprovacaoResponse)
async def get_pagamento_comprovacao(
    pagamento_id: UUID,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    """Movimentacao gerada pela baixa do pagamento, com os anexos visiveis.

    A permissao e a mesma da listagem: engenheiro so alcanca os pagamentos que
    ja consegue ver. Em baixa de lote a resposta e sanitizada — nao expoe o
    detalhamento nem os anexos dos demais pagamentos do lote.
    """
    try:
        result = await svc.get_pagamento_comprovacao(
            pagamento_id, user.team.id, actor_user=user,
        )
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    return ComprovacaoResponse(
        movimentacao=(
            ComprovacaoMovimentacaoResponse(**result.movimentacao.model_dump())
            if result.movimentacao else None
        ),
        attachments=[
            ComprovacaoAttachmentResponse(**a.model_dump()) for a in result.attachments
        ],
    )


@router.put("/pagamentos/{pagamento_id}", response_model=PagamentoResponse)
async def update_pagamento(
    pagamento_id: UUID,
    body: UpdatePagamentoRequest,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    """Edita um pagamento agendado. Restrito a ADMIN e FIN."""
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id, actor_user=user)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    dto = EditPagamentoDTO(
        title=body.title,
        details=body.details,
        valor=body.valor,
        classe=body.classe,
        data_agendada=body.data_agendada,
        payment_cod=body.payment_cod,
        obra_id=body.obra_id,
        requires_receipt=body.requires_receipt,
        apply_to=body.apply_to,
    )
    try:
        updated = await svc.edit_pagamento(pag, dto, actor_user=user)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    return _pag_response(updated)


@router.delete("/pagamentos/{pagamento_id}", response_model=MessageResponse)
async def delete_pagamento(
    pagamento_id: UUID,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
    scope: Annotated[
        Literal["self", "parcelamento"],
        Query(description="'self' remove so este pagamento; 'parcelamento' remove todas as parcelas aguardando do grupo"),
    ] = "self",
):
    """Remove um pagamento agendado ainda nao pago. Restrito ao tenant do usuario."""
    try:
        removidos = await svc.delete_pagamento(
            pagamento_id, user.team.id, actor_user=user, scope=scope,
        )
    except DomainError as e:
        detail = str(e)
        if "nao encontrado" in detail.lower() or "não encontrado" in detail.lower():
            raise HTTPException(status_code=404, detail="Pagamento nao encontrado")
        raise HTTPException(status_code=400, detail=detail)

    redis = get_redis()
    await _invalidate_pagamentos_cache(redis, user.team.id)
    if removidos > 1:
        return MessageResponse(message=f"{removidos} parcelas removidas com sucesso")
    return MessageResponse(message="Pagamento removido com sucesso")


@router.patch("/pagamentos/{pagamento_id}/pay", response_model=PayPagamentoResponse)
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
    return PayPagamentoResponse(
        id=mov.id, title=mov.title, type=mov.type,
        valor=mov.valor.amount, classe=mov.classe,
        natureza=mov.natureza, obra_id=mov.obra_id,
        pagamento_id=pag.id,
        data_movimentacao=mov.data_movimentacao,
        requires_receipt=pag.requires_receipt,
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
        comprovante_pendente_count=resultado.comprovante_pendente_count,
    )


@router.post("/relatorios/comissao-obras", response_model=CreateCommissionReportResponse, status_code=202)
@limiter.limit("10/minute")
async def create_commission_report(
    request: Request,
    body: CreateCommissionReportRequest,
    user: FinanceiroUser,
    use_case: GenerateCommissionReportUseCaseDep,
):
    try:
        result = await use_case.execute(
            GenerateMonthlyCommissionReportInput(
                user_id=user.id,
                team_id=user.team.id,
                categoria_id=body.categoria_id,
                mes=body.mes,
                ano=body.ano,
                porcentagem_comissao=body.porcentagem_comissao,
            )
        )
        return CreateCommissionReportResponse(job_id=result.job_id)
    except DomainError as e:
        detail = str(getattr(e, "detail", e))
        status_code = 404 if "categoria" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        raise HTTPException(status_code=503, detail="Fila de processamento indisponivel")


@router.get("/relatorios/jobs/{job_id}", response_model=CommissionReportJobStatusResponse)
async def get_commission_report_job_status(
    job_id: UUID,
    user: FinanceiroUser,
    use_case: CommissionReportJobStatusUseCaseDep,
):
    try:
        result = await use_case.execute(
            GetCommissionReportJobStatusInput(
                team_id=user.team.id,
                job_id=job_id,
            )
        )
        return CommissionReportJobStatusResponse(
            status=result.status,
            file_url=result.file_url,
            error_message=result.error_message,
        )
    except DomainError as e:
        raise HTTPException(status_code=404, detail=str(getattr(e, "detail", e)))


# ── Pagamentos Agendados — Anexos ─────────────────────────────────────────────

@router.post("/pagamentos/{pagamento_id}/attachments", response_model=PagamentoAttachmentResponse, status_code=201)
async def add_pagamento_attachment(
    pagamento_id: UUID,
    body: CreatePagamentoAttachmentRequest,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    """Anexa um arquivo (PDF/imagem) a um pagamento agendado ainda não pago.

    Engenheiro só anexa em pagamentos que ele mesmo criou; Admin/Financeiro em
    qualquer pagamento do time.
    """
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id, actor_user=user)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    dto = AddPagamentoAttachmentDTO(
        file_path=body.file_path, file_name=body.file_name, content_type=body.content_type,
        replicate_parcelamento=body.replicate_parcelamento,
    )
    try:
        criados = await svc.add_pagamento_attachment(pag, dto)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
    att = criados[0]

    redis = get_redis()
    for criado in criados:
        await _invalidate_pagamento_attachments_cache(redis, user.team.id, criado.pagamento_id)
    return PagamentoAttachmentResponse(
        id=att.id, pagamento_id=att.pagamento_id,
        file_path=att.file_path, file_name=att.file_name,
        content_type=att.content_type, created_at=att.created_at,
    )


@router.get("/pagamentos/{pagamento_id}/attachments", response_model=list[PagamentoAttachmentResponse])
async def list_pagamento_attachments(
    pagamento_id: UUID,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    """Lista anexos de um pagamento agendado. Cache Redis 10min."""
    redis = get_redis()
    cache_key = pagamento_attachments_key(user.team.id, pagamento_id)
    cached = await redis.get(cache_key)
    if cached:
        return [PagamentoAttachmentResponse.model_validate(a) for a in json.loads(cached)]

    try:
        await svc.get_pagamento(pagamento_id, user.team.id, actor_user=user)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    atts = await svc.get_pagamento_attachments(pagamento_id)
    result = [
        PagamentoAttachmentResponse(
            id=a.id, pagamento_id=a.pagamento_id,
            file_path=a.file_path, file_name=a.file_name,
            content_type=a.content_type, created_at=a.created_at,
        ) for a in atts
    ]
    await redis.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in result]),
        ex=600,
    )
    return result


@router.delete("/pagamentos/{pagamento_id}/attachments/{attachment_id}")
async def delete_pagamento_attachment(
    pagamento_id: UUID,
    attachment_id: UUID,
    user: ManagerUser,
    svc: FinanceiroServiceDep,
):
    try:
        pag = await svc.get_pagamento(pagamento_id, user.team.id, actor_user=user)
    except DomainError:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    try:
        await svc.delete_pagamento_attachment(attachment_id, pag)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    redis = get_redis()
    await _invalidate_pagamento_attachments_cache(redis, user.team.id, pagamento_id)
    return MessageResponse(message="Anexo removido com sucesso")


def _pag_response(p) -> PagamentoResponse:
    return PagamentoResponse(
        id=p.id, title=p.title, details=p.details,
        valor=p.valor.amount, classe=p.classe, status=p.status,
        data_agendada=p.data_agendada, payment_cod=p.payment_cod,
        obra_id=p.obra_id, diarist_id=p.diarist_id,
        payment_date=p.payment_date,
        created_by_user_id=p.created_by_user_id,
        created_by_role=p.created_by_role,
        created_by_name=p.created_by_name,
        created_by_engineer=p.created_by_engineer,
        created_at=p.created_at,
        parcelamento_id=p.parcelamento_id,
        parcela_numero=p.parcela_numero,
        parcela_total=p.parcela_total,
        requires_receipt=p.requires_receipt,
        receipt_attached=p.receipt_attached,
    )


def _pag_read_response(p) -> PagamentoReadResponse:
    return PagamentoReadResponse(
        id=p.id, title=p.title, details=p.details,
        valor=p.valor.amount, classe=p.classe, status=p.status,
        data_agendada=p.data_agendada, payment_cod=p.payment_cod,
        pix_copy_and_past=p.pix_copy_and_past,
        obra_id=p.obra_id, diarist_id=p.diarist_id,
        payment_date=p.payment_date,
        created_by_user_id=p.created_by_user_id,
        created_by_role=p.created_by_role,
        created_by_name=p.created_by_name,
        created_by_engineer=p.created_by_engineer,
        created_at=p.created_at,
        parcelamento_id=p.parcelamento_id,
        parcela_numero=p.parcela_numero,
        parcela_total=p.parcela_total,
        requires_receipt=p.requires_receipt,
        receipt_attached=p.receipt_attached,
    )
