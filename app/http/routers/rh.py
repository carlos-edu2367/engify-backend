from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from app.core.limiter import limiter
from app.core.config import settings

from app.application.dtos.rh import (
    AjustePontoFiltersDTO,
    AtestadoFiltersDTO,
    CreateFuncionarioDTO,
    CreateAjustePontoDTO,
    CreateAtestadoDTO,
    CreateFeriasDTO,
    CreateLocalPontoDTO,
    CreateTipoAtestadoDTO,
    FeriasFiltersDTO,
    RhAuditLogFiltersDTO,
    HoleriteFiltersDTO,
    RegistrarPontoDTO,
    ReplaceHorarioTrabalhoDTO,
    TurnoHorarioDTO,
    UpdateHoleriteAjustesDTO,
    UpdateFuncionarioDTO,
    UpdateLocalPontoDTO,
    UpdateTipoAtestadoDTO,
)
from app.application.services.rh_ponto_service import RequestContext, hash_ip
from app.application.providers.utility.storage_provider import DirectUploadRequest
from app.domain.entities.rh import AjustePonto, Atestado, Beneficio, FaixaEncargo, Ferias, Funcionario, Holerite, HoleriteItem, HorarioTrabalho, LocalPonto, RegistroPonto, RegraEncargo, RhFolhaJob, StatusAjuste, StatusAtestado, StatusBeneficio, StatusFerias, StatusHolerite, StatusPonto, StatusRegraEncargo, TabelaProgressiva, TipoAtestado
from app.domain.errors import DomainError
from app.http.dependencies.auth import CurrentUser, RHAdminUser
from app.http.dependencies.pagination import Pagination
from app.http.dependencies.services import RhDashboardServiceDep, RhEncargoServiceDep, RhFolhaServiceDep, RhFuncionarioServiceDep, RhLocalPontoServiceDep, RhPontoServiceDep, RhSolicitacoesServiceDep, StorageProviderDep
from app.http.schemas.common import MessageResponse, PaginatedResponse
from app.http.schemas.rh import (
    RhFuncionarioCreateRequest,
    RhFuncionarioListItem,
    RhFuncionarioResponse,
    RhLocalPontoCreateRequest,
    RhLocalPontoResponse,
    RhLocalPontoUpdateRequest,
    RhPontoCreateRequest,
    RhPontoResponse,
    RhRegistroPontoListItem,
    RhFuncionarioUpdateRequest,
    RhHorarioTrabalhoRequest,
    RhHorarioTrabalhoResponse,
    RhIntervaloHorarioResponse,
    RhAjustePontoCreateRequest,
    RhAjustePontoResponse,
    RhAtestadoCreateRequest,
    RhAtestadoConfirmarUploadRequest,
    RhAtestadoEntregarRequest,
    RhAtestadoDownloadUrlResponse,
    RhAtestadoResponse,
    RhAtestadoUploadUrlRequest,
    RhAtestadoUploadUrlResponse,
    RhAuditLogResponse,
    RhBeneficioCreateRequest,
    RhBeneficioResponse,
    RhBeneficioUpdateRequest,
    RhDashboardSummaryResponse,
    RhFecharFolhaRequest,
    RhFeriasCreateRequest,
    RhFeriasResponse,
    RhFolhaGerarRequest,
    RhFolhaJobCreateRequest,
    RhFolhaJobResponse,
    RhHoleriteItemResponse,
    RhHoleriteSnapshotResponse,
    RhHoleriteAjustesRequest,
    RhHoleriteResponse,
    RhMeResumoResponse,
    RhMeVinculoResponse,
    RhMotivoRequest,
    RhPontoDiaDetalheResponse,
    RhRegraEncargoCreateRequest,
    RhRegraEncargoListItem,
    RhRegraEncargoNovaVersaoRequest,
    RhRegraEncargoResponse,
    RhRegraEncargoUpdateRequest,
    RhTabelaProgressivaCreateRequest,
    RhTabelaProgressivaFaixasRequest,
    RhTabelaProgressivaResponse,
    RhTabelaProgressivaUpdateRequest,
    RhAplicabilidadeResponse,
    RhFaixaEncargoResponse,
    RhTipoAtestadoCreateRequest,
    RhTipoAtestadoResponse,
    RhTipoAtestadoUpdateRequest,
    RhTurnoHorarioResponse,
    RhUsuarioVinculadoResponse,
)


router = APIRouter(prefix="/rh", tags=["RH"])


@router.get("/funcionarios", response_model=PaginatedResponse[RhFuncionarioListItem])
async def list_funcionarios(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhFuncionarioServiceDep,
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
):
    items, total = await svc.list_funcionarios(
        current_user=user,
        page=pagination.page,
        limit=pagination.limit,
        search=search,
        is_active=is_active,
    )
    return PaginatedResponse.build(
        items=[_to_funcionario_list_item(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/funcionarios", response_model=RhFuncionarioResponse, status_code=201)
async def create_funcionario(
    body: RhFuncionarioCreateRequest,
    user: RHAdminUser,
    svc: RhFuncionarioServiceDep,
):
    try:
        funcionario = await svc.create_funcionario(_to_create_dto(body), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_funcionario_response(funcionario)


@router.get("/funcionarios/{funcionario_id}", response_model=RhFuncionarioResponse)
async def get_funcionario(
    funcionario_id: UUID,
    user: RHAdminUser,
    svc: RhFuncionarioServiceDep,
):
    try:
        funcionario = await svc.get_funcionario(funcionario_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_funcionario_response(funcionario)


@router.patch("/funcionarios/{funcionario_id}", response_model=RhFuncionarioResponse)
async def update_funcionario(
    funcionario_id: UUID,
    body: RhFuncionarioUpdateRequest,
    user: RHAdminUser,
    svc: RhFuncionarioServiceDep,
):
    try:
        funcionario = await svc.update_funcionario(funcionario_id, _to_update_dto(body), user, reason=body.reason)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_funcionario_response(funcionario)


@router.delete("/funcionarios/{funcionario_id}", response_model=MessageResponse)
async def delete_funcionario(
    funcionario_id: UUID,
    user: RHAdminUser,
    svc: RhFuncionarioServiceDep,
):
    try:
        await svc.delete_funcionario(funcionario_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return MessageResponse(message="Funcionario removido com sucesso")


@router.get("/funcionarios/{funcionario_id}/horario", response_model=RhHorarioTrabalhoResponse)
async def get_horario(
    funcionario_id: UUID,
    user: RHAdminUser,
    svc: RhFuncionarioServiceDep,
):
    try:
        horario = await svc.get_horario(funcionario_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_horario_response(horario)


@router.put("/funcionarios/{funcionario_id}/horario", response_model=RhHorarioTrabalhoResponse)
async def replace_horario(
    funcionario_id: UUID,
    body: RhHorarioTrabalhoRequest,
    user: RHAdminUser,
    svc: RhFuncionarioServiceDep,
):
    try:
        horario = await svc.replace_horario(
            funcionario_id,
            ReplaceHorarioTrabalhoDTO(turnos=[TurnoHorarioDTO(**turno.model_dump()) for turno in body.turnos]),
            user,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_horario_response(horario)


def _to_create_dto(body: RhFuncionarioCreateRequest) -> CreateFuncionarioDTO:
    return CreateFuncionarioDTO(
        nome=body.nome,
        cpf=body.cpf,
        cargo=body.cargo,
        salario_base=body.salario_base,
        data_admissao=body.data_admissao,
        user_id=body.user_id,
        horario_trabalho=[TurnoHorarioDTO(**turno.model_dump()) for turno in body.horario_trabalho.turnos],
    )


def _to_update_dto(body: RhFuncionarioUpdateRequest) -> UpdateFuncionarioDTO:
    return UpdateFuncionarioDTO(**body.model_dump(exclude_unset=True))


def _to_create_local_dto(body: RhLocalPontoCreateRequest) -> CreateLocalPontoDTO:
    return CreateLocalPontoDTO(**body.model_dump())


def _to_update_local_dto(body: RhLocalPontoUpdateRequest) -> UpdateLocalPontoDTO:
    return UpdateLocalPontoDTO(**body.model_dump(exclude_unset=True))


def _to_funcionario_list_item(funcionario: Funcionario) -> RhFuncionarioListItem:
    return RhFuncionarioListItem(
        id=funcionario.id,
        nome=funcionario.nome,
        cpf_mascarado=_mask_cpf(funcionario.cpf.value),
        cargo=funcionario.cargo,
        salario_base=funcionario.salario_base.amount,
        data_admissao=funcionario.data_admissao.date(),
        user_id=funcionario.user_id,
        is_active=funcionario.is_active,
    )


def _to_funcionario_response(funcionario: Funcionario) -> RhFuncionarioResponse:
    usuario_vinculado = getattr(funcionario, "usuario_vinculado", None)
    return RhFuncionarioResponse(
        id=funcionario.id,
        nome=funcionario.nome,
        cpf=funcionario.cpf.value,
        cpf_mascarado=_mask_cpf(funcionario.cpf.value),
        cargo=funcionario.cargo,
        salario_base=funcionario.salario_base.amount,
        data_admissao=funcionario.data_admissao.date(),
        user_id=funcionario.user_id,
        usuario_vinculado=(
            RhUsuarioVinculadoResponse(
                nome=usuario_vinculado.nome,
                email=usuario_vinculado.email,
                avatar_url=getattr(usuario_vinculado, "avatar_url", None),
            )
            if usuario_vinculado is not None
            else None
        ),
        is_active=funcionario.is_active,
        horario_trabalho=(
            _to_horario_response(funcionario.horario_trabalho)
            if funcionario.horario_trabalho is not None
            else None
        ),
    )


def _to_horario_response(horario: HorarioTrabalho) -> RhHorarioTrabalhoResponse:
    return RhHorarioTrabalhoResponse(
        id=horario.id,
        funcionario_id=horario.funcionario_id,
        turnos=[
            RhTurnoHorarioResponse(
                dia_semana=turno.dia_semana,
                hora_entrada=turno.hora_entrada,
                hora_saida=turno.hora_saida,
                intervalos=[
                    RhIntervaloHorarioResponse(
                        hora_inicio=intervalo.hora_inicio,
                        hora_fim=intervalo.hora_fim,
                    )
                    for intervalo in turno.intervalos
                ],
            )
            for turno in horario.turnos
        ],
    )


def _to_local_response(local: LocalPonto) -> RhLocalPontoResponse:
    return RhLocalPontoResponse(
        id=local.id,
        funcionario_id=local.funcionario_id,
        nome=local.nome,
        latitude=local.latitude,
        longitude=local.longitude,
        raio_metros=local.raio_metros,
    )


def _to_registro_item(registro: RegistroPonto) -> RhRegistroPontoListItem:
    return RhRegistroPontoListItem(
        id=registro.id,
        funcionario_id=registro.funcionario_id,
        tipo=registro.tipo,
        timestamp=registro.timestamp,
        status=registro.status,
        local_ponto_id=registro.local_ponto_id,
        local_ponto_nome=getattr(registro, "local_ponto_nome", None),
        fora_local_autorizado=getattr(registro, "fora_local_autorizado", None),
        latitude=registro.latitude,
        longitude=registro.longitude,
        gps_accuracy_meters=registro.gps_accuracy_meters,
    )


def _to_ponto_response(registro: RegistroPonto) -> RhPontoResponse:
    return RhPontoResponse(
        id=registro.id,
        tipo=registro.tipo,
        timestamp=registro.timestamp,
        status=registro.status,
        local_ponto_id=registro.local_ponto_id,
        message="Ponto registrado com sucesso",
    )


def _to_ferias_response(ferias: Ferias) -> RhFeriasResponse:
    return RhFeriasResponse(
        id=ferias.id,
        funcionario_id=ferias.funcionario_id,
        data_inicio=ferias.data_inicio,
        data_fim=ferias.data_fim,
        status=ferias.status,
        motivo_rejeicao=ferias.motivo_rejeicao,
    )


def _to_ajuste_response(ajuste: AjustePonto) -> RhAjustePontoResponse:
    return RhAjustePontoResponse(
        id=ajuste.id,
        funcionario_id=ajuste.funcionario_id,
        data_referencia=ajuste.data_referencia,
        justificativa=ajuste.justificativa,
        hora_entrada_solicitada=ajuste.hora_entrada_solicitada,
        hora_saida_solicitada=ajuste.hora_saida_solicitada,
        status=ajuste.status,
        motivo_rejeicao=ajuste.motivo_rejeicao,
    )


def _to_tipo_atestado_response(tipo: TipoAtestado) -> RhTipoAtestadoResponse:
    return RhTipoAtestadoResponse(
        id=tipo.id,
        nome=tipo.nome,
        prazo_entrega_dias=tipo.prazo_entrega_dias,
        abona_falta=tipo.abona_falta,
        descricao=tipo.descricao,
    )


def _to_atestado_response(atestado: Atestado) -> RhAtestadoResponse:
    return RhAtestadoResponse(
        id=atestado.id,
        funcionario_id=atestado.funcionario_id,
        tipo_atestado_id=atestado.tipo_atestado_id,
        data_inicio=atestado.data_inicio,
        data_fim=atestado.data_fim,
        status=atestado.status,
        motivo_rejeicao=atestado.motivo_rejeicao,
        has_file=bool(atestado.file_path),
    )


def _to_holerite_response(holerite: Holerite, include_hash: bool = True) -> RhHoleriteResponse:
    return RhHoleriteResponse(
        id=holerite.id,
        funcionario_id=holerite.funcionario_id,
        mes_referencia=holerite.mes_referencia,
        ano_referencia=holerite.ano_referencia,
        salario_base=holerite.salario_base.amount,
        horas_extras=holerite.horas_extras.amount,
        descontos_falta=holerite.descontos_falta.amount,
        acrescimos_manuais=holerite.acrescimos_manuais.amount,
        descontos_manuais=holerite.descontos_manuais.amount,
        valor_liquido=holerite.valor_liquido.amount,
        status=holerite.status,
        pagamento_agendado_id=holerite.pagamento_agendado_id,
        valor_bruto=holerite.valor_bruto.amount,
        total_proventos=holerite.total_proventos.amount,
        total_descontos=holerite.total_descontos.amount,
        total_informativos=holerite.total_informativos.amount,
        calculation_version=holerite.calculation_version,
        calculation_hash=holerite.calculation_hash if include_hash else None,
        calculated_at=holerite.calculated_at,
    )


def _to_folha_job_response(job: RhFolhaJob) -> RhFolhaJobResponse:
    return RhFolhaJobResponse(
        id=job.id,
        mes=job.mes,
        ano=job.ano,
        status=job.status,
        total_funcionarios=job.total_funcionarios,
        processados=job.processados,
        falhas=job.falhas,
        error_summary=job.error_summary,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


def _to_aplicabilidade_response(item) -> RhAplicabilidadeResponse:
    return RhAplicabilidadeResponse(id=getattr(item, "id", None), escopo=item.escopo, valor=item.valor)


def _to_beneficio_response(beneficio: Beneficio) -> RhBeneficioResponse:
    return RhBeneficioResponse(
        id=beneficio.id,
        nome=beneficio.nome,
        descricao=beneficio.descricao,
        status=beneficio.status,
    )


def _to_regra_encargo_response(regra: RegraEncargo) -> RhRegraEncargoResponse:
    return RhRegraEncargoResponse(
        id=regra.id,
        regra_grupo_id=regra.regra_grupo_id,
        codigo=regra.codigo,
        nome=regra.nome,
        descricao=regra.descricao,
        tipo_calculo=regra.tipo_calculo,
        natureza=regra.natureza,
        base_calculo=regra.base_calculo,
        prioridade=regra.prioridade,
        status=regra.status,
        vigencia_inicio=regra.vigencia_inicio,
        vigencia_fim=regra.vigencia_fim,
        valor_fixo=regra.valor_fixo.amount if regra.valor_fixo else None,
        percentual=regra.percentual,
        tabela_progressiva_id=regra.tabela_progressiva_id,
        tabela_progressiva_nome=regra.tabela_progressiva.nome if regra.tabela_progressiva else None,
        teto=regra.teto.amount if regra.teto else None,
        piso=regra.piso.amount if regra.piso else None,
        arredondamento=regra.arredondamento,
        incide_no_liquido=regra.incide_no_liquido,
        aplicabilidades=[_to_aplicabilidade_response(item) for item in regra.aplicabilidades],
    )


def _to_faixa_response(faixa: FaixaEncargo) -> RhFaixaEncargoResponse:
    return RhFaixaEncargoResponse(
        id=faixa.id,
        ordem=faixa.ordem,
        valor_inicial=faixa.valor_inicial.amount,
        valor_final=faixa.valor_final.amount if faixa.valor_final else None,
        aliquota=faixa.aliquota,
        deducao=faixa.deducao.amount,
        calculo_marginal=faixa.calculo_marginal,
    )


def _to_tabela_progressiva_response(tabela: TabelaProgressiva) -> RhTabelaProgressivaResponse:
    return RhTabelaProgressivaResponse(
        id=tabela.id,
        codigo=tabela.codigo,
        nome=tabela.nome,
        descricao=tabela.descricao,
        status=tabela.status,
        vigencia_inicio=tabela.vigencia_inicio,
        vigencia_fim=tabela.vigencia_fim,
        faixas=[_to_faixa_response(item) for item in tabela.faixas],
    )


def _to_holerite_item_response(item: HoleriteItem) -> RhHoleriteItemResponse:
    snapshot = item.snapshot_regra or {}
    return RhHoleriteItemResponse(
        id=item.id,
        holerite_id=item.holerite_id,
        funcionario_id=item.funcionario_id,
        tipo=item.tipo,
        origem=item.origem,
        codigo=item.codigo,
        descricao=item.descricao,
        natureza=item.natureza,
        ordem=item.ordem,
        base=item.base.amount,
        valor=item.valor.amount,
        regra_encargo_id=item.regra_encargo_id,
        regra_grupo_id=item.regra_grupo_id,
        regra_nome=snapshot.get("nome") if isinstance(snapshot, dict) else None,
        regra_versao=snapshot.get("version") or snapshot.get("vigencia_inicio") if isinstance(snapshot, dict) else None,
        is_automatico=item.is_automatico,
    )


def _to_dashboard_response(summary) -> RhDashboardSummaryResponse:
    if isinstance(summary, dict):
        return RhDashboardSummaryResponse(**summary)
    return RhDashboardSummaryResponse(**summary.model_dump())


def _to_me_resumo_response(summary) -> RhMeResumoResponse:
    if isinstance(summary, dict):
        return RhMeResumoResponse(**summary)
    return RhMeResumoResponse(**summary.model_dump())


def _to_audit_log_response(item) -> RhAuditLogResponse:
    if isinstance(item, dict):
        return RhAuditLogResponse(**item)
    return RhAuditLogResponse(**item.model_dump())


def _mask_cpf(cpf: str) -> str:
    digits = "".join(ch for ch in cpf if ch.isdigit())
    if len(digits) != 11:
        return "***"
    return f"{digits[:3]}.***.***-{digits[-2:]}"


def _map_rh_error(exc: DomainError) -> HTTPException:
    detail = getattr(exc, "detail", str(exc))
    lowered = detail.lower()
    if any(marker in lowered for marker in ("sql", "constraint", "traceback", "psycopg", "integrityerror")):
        return HTTPException(status_code=400, detail="Nao foi possivel concluir a operacao. Revise os dados informados.")
    if "nao encontrado" in lowered:
        return HTTPException(status_code=404, detail=detail)
    if "ja existe" in lowered or "ja esta vinculado" in lowered:
        return HTTPException(status_code=409, detail=detail)
    if "acesso restrito" in lowered:
        return HTTPException(status_code=403, detail=detail)
    if "funcionario vinculado" in lowered:
        return HTTPException(status_code=403, detail=detail)
    if "fora de um local autorizado" in lowered:
        return HTTPException(status_code=400, detail=detail)
    if "duplicada" in lowered:
        return HTTPException(status_code=409, detail=detail)
    if "conflito" in lowered or "rascunho" in lowered or "fechado" in lowered or "ativa" in lowered:
        return HTTPException(status_code=409, detail=detail)
    if (
        "motivo do ajuste manual" in lowered
        or "motivo da alteracao salarial" in lowered
        or "mes de referencia invalido" in lowered
        or "ano de referencia invalido" in lowered
    ):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=400, detail=detail)


@router.get("/dashboard", response_model=RhDashboardSummaryResponse)
@limiter.limit("30/minute")
async def get_dashboard(
    request: Request,
    user: RHAdminUser,
    svc: RhDashboardServiceDep,
    mes: int = Query(...),
    ano: int = Query(...),
):
    try:
        summary = await svc.obter_dashboard(user, mes, ano)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_dashboard_response(summary)


@router.get("/me/resumo", response_model=RhMeResumoResponse)
@limiter.limit("30/minute")
async def get_meu_resumo(request: Request, user: CurrentUser, svc: RhDashboardServiceDep):
    try:
        summary = await svc.obter_meu_resumo(user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_me_resumo_response(summary)


@router.get("/me/vinculo", response_model=RhMeVinculoResponse)
@limiter.limit("30/minute")
async def get_meu_vinculo(request: Request, user: CurrentUser, svc: RhDashboardServiceDep):
    return RhMeVinculoResponse(**await svc.obter_meu_vinculo(user))


@router.get("/audit-logs", response_model=PaginatedResponse[RhAuditLogResponse])
@limiter.limit("20/minute")
async def list_audit_logs(
    request: Request,
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhDashboardServiceDep,
    entity_type: str | None = Query(default=None),
    entity_id: UUID | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    try:
        items, total = await svc.listar_audit_logs(
            user,
            pagination.page,
            pagination.limit,
            RhAuditLogFiltersDTO(
                entity_type=entity_type,
                entity_id=entity_id,
                actor_user_id=actor_user_id,
                action=action,
                start=start,
                end=end,
            ),
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_audit_log_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/encargos/regras", response_model=PaginatedResponse[RhRegraEncargoListItem])
async def list_regras_encargo(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhEncargoServiceDep,
    search: str | None = Query(default=None),
    codigo: str | None = Query(default=None),
    status: StatusRegraEncargo | None = Query(default=None),
):
    try:
        items, total = await svc.listar_regras(user, pagination.page, pagination.limit, search=search, codigo=codigo, status=status)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_regra_encargo_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/beneficios", response_model=PaginatedResponse[RhBeneficioResponse])
async def list_beneficios(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhEncargoServiceDep,
    status: StatusBeneficio | None = Query(default=None),
    search: str | None = Query(default=None),
):
    try:
        items, total = await svc.listar_beneficios(user, pagination.page, pagination.limit, status=status, search=search)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_beneficio_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/beneficios", response_model=RhBeneficioResponse, status_code=201)
async def create_beneficio(body: RhBeneficioCreateRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        beneficio = await svc.criar_beneficio(user, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_beneficio_response(beneficio)


@router.patch("/beneficios/{beneficio_id}", response_model=RhBeneficioResponse)
async def update_beneficio(beneficio_id: UUID, body: RhBeneficioUpdateRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        beneficio = await svc.atualizar_beneficio(user, beneficio_id, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_beneficio_response(beneficio)


@router.post("/beneficios/{beneficio_id}/inativar", response_model=RhBeneficioResponse)
async def inativar_beneficio(beneficio_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        beneficio = await svc.inativar_beneficio(user, beneficio_id, body.motivo)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_beneficio_response(beneficio)


@router.post("/beneficios/{beneficio_id}/reativar", response_model=RhBeneficioResponse)
async def reativar_beneficio(beneficio_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        beneficio = await svc.reativar_beneficio(user, beneficio_id, body.motivo)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_beneficio_response(beneficio)


@router.post("/encargos/regras", response_model=RhRegraEncargoResponse, status_code=201)
async def create_regra_encargo(body: RhRegraEncargoCreateRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.criar_regra(user, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.get("/encargos/regras/{regra_id}", response_model=RhRegraEncargoResponse)
async def get_regra_encargo(regra_id: UUID, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.obter_regra(user, regra_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.patch("/encargos/regras/{regra_id}", response_model=RhRegraEncargoResponse)
async def update_regra_encargo(regra_id: UUID, body: RhRegraEncargoUpdateRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.atualizar_regra(user, regra_id, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.post("/encargos/regras/{regra_id}/nova-versao", response_model=RhRegraEncargoResponse, status_code=201)
async def criar_nova_versao_regra(regra_id: UUID, body: RhRegraEncargoNovaVersaoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.criar_nova_versao(user, regra_id, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.post("/encargos/regras/{regra_id}/ativar", response_model=RhRegraEncargoResponse)
async def ativar_regra_encargo(regra_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.ativar_regra(user, regra_id, body.motivo)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.post("/encargos/regras/{regra_id}/inativar", response_model=RhRegraEncargoResponse)
async def inativar_regra_encargo(regra_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.inativar_regra(user, regra_id, body.motivo)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.post("/encargos/regras/{regra_id}/arquivar", response_model=RhRegraEncargoResponse)
async def arquivar_regra_encargo(regra_id: UUID, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        regra = await svc.arquivar_regra(user, regra_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_regra_encargo_response(regra)


@router.get("/encargos/tabelas-progressivas", response_model=PaginatedResponse[RhTabelaProgressivaResponse])
async def list_tabelas_progressivas(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhEncargoServiceDep,
    search: str | None = Query(default=None),
    codigo: str | None = Query(default=None),
    status: StatusRegraEncargo | None = Query(default=None),
):
    try:
        items, total = await svc.listar_tabelas_progressivas(user, pagination.page, pagination.limit, search=search, codigo=codigo, status=status)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_tabela_progressiva_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/encargos/tabelas-progressivas", response_model=RhTabelaProgressivaResponse, status_code=201)
async def create_tabela_progressiva(body: RhTabelaProgressivaCreateRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        tabela = await svc.criar_tabela_progressiva(user, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tabela_progressiva_response(tabela)


@router.get("/encargos/tabelas-progressivas/{tabela_id}", response_model=RhTabelaProgressivaResponse)
async def get_tabela_progressiva(tabela_id: UUID, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        tabela = await svc.obter_tabela_progressiva(user, tabela_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tabela_progressiva_response(tabela)


@router.patch("/encargos/tabelas-progressivas/{tabela_id}", response_model=RhTabelaProgressivaResponse)
async def update_tabela_progressiva(tabela_id: UUID, body: RhTabelaProgressivaUpdateRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        tabela = await svc.atualizar_tabela_progressiva(user, tabela_id, body)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tabela_progressiva_response(tabela)


@router.put("/encargos/tabelas-progressivas/{tabela_id}/faixas", response_model=RhTabelaProgressivaResponse)
async def replace_faixas_tabela_progressiva(tabela_id: UUID, body: RhTabelaProgressivaFaixasRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        tabela = await svc.substituir_faixas_tabela(user, tabela_id, body.faixas)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tabela_progressiva_response(tabela)


@router.post("/encargos/tabelas-progressivas/{tabela_id}/ativar", response_model=RhTabelaProgressivaResponse)
async def ativar_tabela_progressiva(tabela_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        tabela = await svc.ativar_tabela_progressiva(user, tabela_id, body.motivo)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tabela_progressiva_response(tabela)


@router.post("/encargos/tabelas-progressivas/{tabela_id}/inativar", response_model=RhTabelaProgressivaResponse)
async def inativar_tabela_progressiva(tabela_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhEncargoServiceDep):
    try:
        tabela = await svc.inativar_tabela_progressiva(user, tabela_id, body.motivo)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tabela_progressiva_response(tabela)


@router.get("/funcionarios/{funcionario_id}/locais-ponto", response_model=PaginatedResponse[RhLocalPontoResponse])
async def list_locais_ponto(
    funcionario_id: UUID,
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhLocalPontoServiceDep,
):
    try:
        items, total = await svc.list_locais(funcionario_id, user, pagination.page, pagination.limit)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_local_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/funcionarios/{funcionario_id}/locais-ponto", response_model=RhLocalPontoResponse, status_code=201)
async def create_local_ponto(
    funcionario_id: UUID,
    body: RhLocalPontoCreateRequest,
    user: RHAdminUser,
    svc: RhLocalPontoServiceDep,
):
    try:
        local = await svc.create_local(funcionario_id, _to_create_local_dto(body), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_local_response(local)


@router.patch("/locais-ponto/{local_id}", response_model=RhLocalPontoResponse)
async def update_local_ponto(
    local_id: UUID,
    body: RhLocalPontoUpdateRequest,
    user: RHAdminUser,
    svc: RhLocalPontoServiceDep,
):
    try:
        local = await svc.update_local(local_id, _to_update_local_dto(body), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_local_response(local)


@router.delete("/locais-ponto/{local_id}", response_model=MessageResponse)
async def delete_local_ponto(
    local_id: UUID,
    user: RHAdminUser,
    svc: RhLocalPontoServiceDep,
):
    try:
        await svc.delete_local(local_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return MessageResponse(message="Local de ponto removido com sucesso")


@router.post("/ponto", response_model=RhPontoResponse)
@limiter.limit("30/minute")
async def registrar_ponto(
    body: RhPontoCreateRequest,
    request: Request,
    user: CurrentUser,
    svc: RhPontoServiceDep,
):
    try:
        registro = await svc.registrar_ponto(
            RegistrarPontoDTO(**body.model_dump()),
            user,
            RequestContext(
                request_id=request.headers.get("X-Request-ID"),
                ip_hash=hash_ip(request.client.host if request.client else None),
                user_agent=request.headers.get("User-Agent"),
                idempotency_key=request.headers.get("Idempotency-Key"),
            ),
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ponto_response(registro)


@router.get("/ponto", response_model=PaginatedResponse[RhRegistroPontoListItem])
async def list_pontos(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhPontoServiceDep,
    funcionario_id: UUID | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    status: StatusPonto | None = Query(default=None),
):
    try:
        items, total = await svc.list_pontos(
            user,
            pagination.page,
            pagination.limit,
            funcionario_id=funcionario_id,
            start=start,
            end=end,
            status=status,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_registro_item(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/ponto/dias", response_model=PaginatedResponse[RhRegistroPontoListItem])
async def list_ponto_dias(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhPontoServiceDep,
    funcionario_id: UUID | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    status: StatusPonto | None = Query(default=None),
):
    try:
        items, total = await svc.listar_dias_ponto(user, pagination.page, pagination.limit, funcionario_id=funcionario_id, start=start, end=end, status=status)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_registro_item(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/ponto/dias/{funcionario_id}/{data}", response_model=RhPontoDiaDetalheResponse)
async def get_ponto_dia(funcionario_id: UUID, data: date, user: RHAdminUser, svc: RhPontoServiceDep):
    try:
        detail = await svc.obter_dia_ponto(user, funcionario_id, data)
    except DomainError as exc:
        raise _map_rh_error(exc)
    funcionario = detail["funcionario"]
    return RhPontoDiaDetalheResponse(
        funcionario_id=funcionario.id,
        funcionario_nome=funcionario.nome,
        funcionario_cpf_mascarado=_mask_cpf(funcionario.cpf.value),
        funcionario_cargo=funcionario.cargo,
        status=detail.get("status", detail.get("status_dia")),
        local_autorizado_nome=detail.get("local_autorizado_nome"),
        registros=[_to_registro_item(item) for item in detail["registros"]],
        locais_autorizados=[_to_local_response(item) for item in detail["locais_autorizados"]],
        ajustes_relacionados=detail["ajustes_relacionados"],
        impacto_estimado=detail["impacto_estimado"],
        auditoria_resumida=detail["auditoria_resumida"],
    )


@router.get("/ponto/registros/{registro_id}")
async def get_ponto_registro(registro_id: UUID, user: RHAdminUser, svc: RhPontoServiceDep):
    try:
        detail = await svc.obter_registro_ponto(user, registro_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    funcionario = detail["funcionario"]
    registro = detail["registro"]
    return {
        "registro": _to_registro_item(registro).model_dump(),
        "funcionario_nome": funcionario.nome,
        "funcionario_cpf_mascarado": _mask_cpf(funcionario.cpf.value),
        "funcionario_cargo": funcionario.cargo,
        "local_ponto_nome": detail["local_ponto"].nome if detail["local_ponto"] else None,
        "auditoria_resumida": detail["auditoria_resumida"],
    }


@router.get("/me/ponto", response_model=PaginatedResponse[RhRegistroPontoListItem])
async def list_meus_pontos(
    user: CurrentUser,
    pagination: Pagination,
    svc: RhPontoServiceDep,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    status: StatusPonto | None = Query(default=None),
):
    try:
        items, total = await svc.list_meus_pontos(user, pagination.page, pagination.limit, start=start, end=end, status=status)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_registro_item(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/ferias", response_model=RhFeriasResponse)
async def request_ferias(
    body: RhFeriasCreateRequest,
    user: CurrentUser,
    svc: RhSolicitacoesServiceDep,
):
    try:
        ferias = await svc.request_ferias(CreateFeriasDTO(**body.model_dump()), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ferias_response(ferias)


@router.get("/ferias", response_model=PaginatedResponse[RhFeriasResponse])
async def list_ferias(
    user: CurrentUser,
    pagination: Pagination,
    svc: RhSolicitacoesServiceDep,
    funcionario_id: UUID | None = Query(default=None),
    status: StatusFerias | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    try:
        items, total = await svc.list_ferias(
            user,
            FeriasFiltersDTO(funcionario_id=funcionario_id, status=status, start=start, end=end),
            pagination.page,
            pagination.limit,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_ferias_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/ferias/{ferias_id}/aprovar", response_model=RhFeriasResponse)
async def approve_ferias(ferias_id: UUID, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        ferias = await svc.approve_ferias(ferias_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ferias_response(ferias)


@router.post("/ferias/{ferias_id}/rejeitar", response_model=RhFeriasResponse)
async def reject_ferias(ferias_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        ferias = await svc.reject_ferias(ferias_id, body.motivo, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ferias_response(ferias)


@router.post("/ferias/{ferias_id}/cancelar", response_model=RhFeriasResponse)
async def cancel_ferias(ferias_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        ferias = await svc.cancel_ferias(ferias_id, body.motivo, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ferias_response(ferias)


@router.post("/ajustes-ponto", response_model=RhAjustePontoResponse, status_code=201)
async def request_ajuste_ponto(
    body: RhAjustePontoCreateRequest,
    user: CurrentUser,
    svc: RhSolicitacoesServiceDep,
):
    try:
        ajuste = await svc.request_ajuste(CreateAjustePontoDTO(**body.model_dump()), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ajuste_response(ajuste)


@router.get("/ajustes-ponto", response_model=PaginatedResponse[RhAjustePontoResponse])
async def list_ajustes_ponto(
    user: CurrentUser,
    pagination: Pagination,
    svc: RhSolicitacoesServiceDep,
    funcionario_id: UUID | None = Query(default=None),
    status: StatusAjuste | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    try:
        items, total = await svc.list_ajustes(
            user,
            AjustePontoFiltersDTO(funcionario_id=funcionario_id, status=status, start=start, end=end),
            pagination.page,
            pagination.limit,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_ajuste_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/ajustes-ponto/{ajuste_id}/aprovar", response_model=RhAjustePontoResponse)
async def approve_ajuste_ponto(ajuste_id: UUID, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        ajuste = await svc.approve_ajuste(ajuste_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ajuste_response(ajuste)


@router.post("/ajustes-ponto/{ajuste_id}/rejeitar", response_model=RhAjustePontoResponse)
async def reject_ajuste_ponto(ajuste_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        ajuste = await svc.reject_ajuste(ajuste_id, body.motivo, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_ajuste_response(ajuste)


@router.get("/tipos-atestado", response_model=PaginatedResponse[RhTipoAtestadoResponse])
async def list_tipos_atestado(user: CurrentUser, pagination: Pagination, svc: RhSolicitacoesServiceDep):
    try:
        items, total = await svc.list_tipos_atestado(user, pagination.page, pagination.limit)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_tipo_atestado_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/tipos-atestado", response_model=RhTipoAtestadoResponse, status_code=201)
async def create_tipo_atestado(body: RhTipoAtestadoCreateRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        tipo = await svc.create_tipo_atestado(CreateTipoAtestadoDTO(**body.model_dump()), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tipo_atestado_response(tipo)


@router.patch("/tipos-atestado/{tipo_id}", response_model=RhTipoAtestadoResponse)
async def update_tipo_atestado(tipo_id: UUID, body: RhTipoAtestadoUpdateRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        tipo = await svc.update_tipo_atestado(tipo_id, UpdateTipoAtestadoDTO(**body.model_dump(exclude_unset=True)), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_tipo_atestado_response(tipo)


@router.delete("/tipos-atestado/{tipo_id}", response_model=MessageResponse)
async def delete_tipo_atestado(tipo_id: UUID, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        await svc.delete_tipo_atestado(tipo_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return MessageResponse(message="Tipo de atestado removido com sucesso")


@router.post("/atestados", response_model=RhAtestadoResponse, status_code=201)
async def create_atestado(body: RhAtestadoCreateRequest, user: CurrentUser, svc: RhSolicitacoesServiceDep):
    try:
        atestado = await svc.create_atestado(CreateAtestadoDTO(**body.model_dump()), user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_atestado_response(atestado)


@router.get("/atestados", response_model=PaginatedResponse[RhAtestadoResponse])
async def list_atestados(
    user: CurrentUser,
    pagination: Pagination,
    svc: RhSolicitacoesServiceDep,
    funcionario_id: UUID | None = Query(default=None),
    tipo_atestado_id: UUID | None = Query(default=None),
    status: StatusAtestado | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    try:
        items, total = await svc.list_atestados(
            user,
            AtestadoFiltersDTO(
                funcionario_id=funcionario_id,
                tipo_atestado_id=tipo_atestado_id,
                status=status,
                start=start,
                end=end,
            ),
            pagination.page,
            pagination.limit,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_atestado_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.post("/atestados/{atestado_id}/entregar", response_model=RhAtestadoResponse)
async def deliver_atestado(atestado_id: UUID, body: RhAtestadoEntregarRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        atestado = await svc.deliver_atestado(atestado_id, body.file_path, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_atestado_response(atestado)


@router.post("/atestados/{atestado_id}/upload-url", response_model=RhAtestadoUploadUrlResponse)
async def create_atestado_upload_url(
    atestado_id: UUID,
    body: RhAtestadoUploadUrlRequest,
    user: CurrentUser,
    svc: RhSolicitacoesServiceDep,
    storage: StorageProviderDep,
):
    try:
        upload = await svc.preparar_upload_atestado(atestado_id, user, body.file_name, body.content_type, body.size_bytes)
        direct = await storage.create_direct_upload(
            DirectUploadRequest(
                bucket=settings.storage_bucket_name,
                path=upload["path"],
                content_type=upload["content_type"],
            )
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return RhAtestadoUploadUrlResponse(upload_url=direct.upload_url, path=direct.path, headers=direct.headers)


@router.post("/atestados/{atestado_id}/confirmar-upload", response_model=RhAtestadoResponse)
async def confirmar_atestado_upload(
    atestado_id: UUID,
    body: RhAtestadoConfirmarUploadRequest,
    user: RHAdminUser,
    svc: RhSolicitacoesServiceDep,
):
    try:
        atestado = await svc.confirmar_upload_atestado(atestado_id, user, body.path, body.content_type, body.size_bytes)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_atestado_response(atestado)


@router.post("/atestados/{atestado_id}/rejeitar", response_model=RhAtestadoResponse)
async def reject_atestado(atestado_id: UUID, body: RhMotivoRequest, user: RHAdminUser, svc: RhSolicitacoesServiceDep):
    try:
        atestado = await svc.reject_atestado(atestado_id, body.motivo, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_atestado_response(atestado)


@router.get("/atestados/{atestado_id}/download-url", response_model=RhAtestadoDownloadUrlResponse)
async def get_atestado_download_url(
    atestado_id: UUID,
    user: CurrentUser,
    svc: RhSolicitacoesServiceDep,
    storage: StorageProviderDep,
):
    try:
        atestado = await svc.obter_atestado_para_download(atestado_id, user)
        download_url = await storage.get_signed_download_url(
            bucket=settings.storage_bucket_name,
            path=atestado.file_path,
            expires_in=settings.storage_download_expires_in,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return RhAtestadoDownloadUrlResponse(
        download_url=download_url,
        expires_in=settings.storage_download_expires_in,
    )


@router.post("/folha/gerar", response_model=list[RhHoleriteResponse])
async def gerar_folha(
    body: RhFolhaGerarRequest,
    user: RHAdminUser,
    svc: RhFolhaServiceDep,
):
    try:
        items = await svc.gerar_rascunho_folha(user, body.mes, body.ano, funcionario_id=body.funcionario_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return [_to_holerite_response(item) for item in items]


@router.post("/folha/jobs", response_model=RhFolhaJobResponse, status_code=202)
async def criar_job_folha(
    body: RhFolhaJobCreateRequest,
    user: RHAdminUser,
    svc: RhFolhaServiceDep,
):
    try:
        job = await svc.criar_job_geracao_folha(user, body.mes, body.ano, funcionario_ids=body.funcionario_ids)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_folha_job_response(job)


@router.get("/folha/jobs", response_model=PaginatedResponse[RhFolhaJobResponse])
async def listar_jobs_folha(user: RHAdminUser, pagination: Pagination, svc: RhFolhaServiceDep):
    try:
        items, total = await svc.listar_jobs_geracao_folha(user, pagination.page, pagination.limit)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_folha_job_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/folha/jobs/{job_id}", response_model=RhFolhaJobResponse)
async def obter_job_folha(
    job_id: UUID,
    user: RHAdminUser,
    svc: RhFolhaServiceDep,
):
    try:
        job = await svc.obter_job_geracao_folha(user, job_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_folha_job_response(job)


@router.post("/folha/jobs/{job_id}/cancelar", response_model=RhFolhaJobResponse)
async def cancelar_job_folha(job_id: UUID, user: RHAdminUser, svc: RhFolhaServiceDep):
    try:
        job = await svc.cancelar_job_geracao_folha(user, job_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_folha_job_response(job)


@router.post("/folha/jobs/{job_id}/retry-falhas", response_model=RhFolhaJobResponse, status_code=202)
async def retry_falhas_job_folha(job_id: UUID, user: RHAdminUser, svc: RhFolhaServiceDep):
    try:
        job = await svc.retry_falhas_job_geracao_folha(user, job_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_folha_job_response(job)


@router.get("/folha", response_model=PaginatedResponse[RhHoleriteResponse])
async def list_folha(
    user: RHAdminUser,
    pagination: Pagination,
    svc: RhFolhaServiceDep,
    mes: int = Query(...),
    ano: int = Query(...),
    funcionario_id: UUID | None = Query(default=None),
    status: StatusHolerite | None = Query(default=None),
):
    try:
        items, total = await svc.listar_holerites(user, mes, ano, status, pagination.page, pagination.limit, funcionario_id=funcionario_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_holerite_response(item) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/holerites/{holerite_id}", response_model=RhHoleriteResponse)
async def get_holerite(holerite_id: UUID, user: RHAdminUser, svc: RhFolhaServiceDep):
    try:
        holerite = await svc.obter_holerite(holerite_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_holerite_response(holerite)


@router.get("/holerites/{holerite_id}/itens", response_model=list[RhHoleriteItemResponse])
async def list_holerite_itens(holerite_id: UUID, user: RHAdminUser, svc: RhFolhaServiceDep):
    try:
        itens = await svc.listar_itens_holerite(user, holerite_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return [_to_holerite_item_response(item) for item in itens]


@router.get("/holerites/{holerite_id}/itens/{item_id}/snapshot", response_model=RhHoleriteSnapshotResponse)
async def get_holerite_item_snapshot(holerite_id: UUID, item_id: UUID, user: RHAdminUser, svc: RhFolhaServiceDep):
    try:
        snapshot = await svc.obter_snapshot_item(user, holerite_id, item_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return RhHoleriteSnapshotResponse(**snapshot)


@router.patch("/holerites/{holerite_id}/ajustes-manuais", response_model=RhHoleriteResponse)
async def update_holerite_ajustes(
    holerite_id: UUID,
    body: RhHoleriteAjustesRequest,
    user: RHAdminUser,
    svc: RhFolhaServiceDep,
):
    try:
        holerite = await svc.atualizar_ajustes_manuais(
            holerite_id,
            body.acrescimos_manuais,
            body.descontos_manuais,
            user,
            body.motivo,
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_holerite_response(holerite)


@router.post("/folha/fechar", response_model=list[RhHoleriteResponse])
async def fechar_folha(
    body: RhFecharFolhaRequest,
    request: Request,
    user: RHAdminUser,
    svc: RhFolhaServiceDep,
):
    try:
        items = await svc.fechar_folha(
            user,
            body.mes,
            body.ano,
            funcionario_ids=body.funcionario_ids,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except DomainError as exc:
        raise _map_rh_error(exc)
    return [_to_holerite_response(item) for item in items]


@router.get("/me/holerites", response_model=PaginatedResponse[RhHoleriteResponse])
async def list_meus_holerites(
    user: CurrentUser,
    pagination: Pagination,
    svc: RhFolhaServiceDep,
):
    try:
        items, total = await svc.listar_meus_holerites(user, pagination.page, pagination.limit)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return PaginatedResponse.build(
        items=[_to_holerite_response(item, include_hash=False) for item in items],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get("/me/holerites/{holerite_id}", response_model=RhHoleriteResponse)
async def get_meu_holerite(holerite_id: UUID, user: CurrentUser, svc: RhFolhaServiceDep):
    try:
        holerite = await svc.obter_meu_holerite(holerite_id, user)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return _to_holerite_response(holerite, include_hash=False)


@router.get("/me/holerites/{holerite_id}/itens", response_model=list[RhHoleriteItemResponse])
async def list_meu_holerite_itens(holerite_id: UUID, user: CurrentUser, svc: RhFolhaServiceDep):
    try:
        itens = await svc.listar_itens_holerite(user, holerite_id)
    except DomainError as exc:
        raise _map_rh_error(exc)
    return [_to_holerite_item_response(item) for item in itens]
