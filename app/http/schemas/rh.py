from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.rh import (
    BaseCalculoEncargo,
    EscopoAplicabilidade,
    HoleriteItemNatureza,
    HoleriteItemTipo,
    NaturezaEncargo,
    RhFolhaJobStatus,
    StatusBeneficio,
    StatusAjuste,
    StatusAtestado,
    StatusFerias,
    StatusHolerite,
    StatusPonto,
    StatusRegraEncargo,
    TipoPonto,
    TipoRegraEncargo,
)


class RhIntervaloHorarioRequest(BaseModel):
    hora_inicio: time
    hora_fim: time


class RhTurnoHorarioRequest(BaseModel):
    dia_semana: int
    hora_entrada: time
    hora_saida: time
    intervalos: list[RhIntervaloHorarioRequest] = Field(default_factory=list)


class RhHorarioTrabalhoRequest(BaseModel):
    turnos: list[RhTurnoHorarioRequest] = Field(min_length=1)


class RhFuncionarioCreateRequest(BaseModel):
    nome: str
    cpf: str
    cargo: str
    salario_base: Decimal
    data_admissao: date
    user_id: UUID | None = None
    horario_trabalho: RhHorarioTrabalhoRequest


class RhFuncionarioUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    cpf: str | None = None
    cargo: str | None = None
    salario_base: Decimal | None = None
    data_admissao: date | None = None
    user_id: UUID | None = None
    is_active: bool | None = None
    reason: str | None = None


class RhIntervaloHorarioResponse(BaseModel):
    hora_inicio: time
    hora_fim: time


class RhTurnoHorarioResponse(BaseModel):
    dia_semana: int
    hora_entrada: time
    hora_saida: time
    intervalos: list[RhIntervaloHorarioResponse] = Field(default_factory=list)


class RhHorarioTrabalhoResponse(BaseModel):
    id: UUID
    funcionario_id: UUID
    turnos: list[RhTurnoHorarioResponse]


class RhFuncionarioListItem(BaseModel):
    id: UUID
    nome: str
    cpf_mascarado: str
    cargo: str
    salario_base: Decimal
    data_admissao: date
    user_id: UUID | None = None
    is_active: bool


class RhUsuarioVinculadoResponse(BaseModel):
    nome: str
    email: str
    avatar_url: str | None = None


class RhFuncionarioResponse(BaseModel):
    id: UUID
    nome: str
    cpf: str
    cpf_mascarado: str
    cargo: str
    salario_base: Decimal
    data_admissao: date
    user_id: UUID | None = None
    usuario_vinculado: RhUsuarioVinculadoResponse | None = None
    is_active: bool
    horario_trabalho: RhHorarioTrabalhoResponse | None = None


class RhLocalPontoCreateRequest(BaseModel):
    nome: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    raio_metros: float = Field(default=100, ge=20, le=1000)


class RhLocalPontoUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    raio_metros: float | None = Field(default=None, ge=20, le=1000)


class RhLocalPontoResponse(BaseModel):
    id: UUID
    funcionario_id: UUID
    nome: str
    latitude: float
    longitude: float
    raio_metros: float


class RhPontoCreateRequest(BaseModel):
    tipo: TipoPonto
    latitude: float
    longitude: float
    client_timestamp: datetime | None = None
    gps_accuracy_meters: float | None = None
    device_fingerprint: str | None = None


class RhPontoResponse(BaseModel):
    id: UUID
    tipo: TipoPonto
    timestamp: datetime
    status: StatusPonto
    local_ponto_id: UUID | None = None
    message: str


class RhRegistroPontoListItem(BaseModel):
    id: UUID
    funcionario_id: UUID
    tipo: TipoPonto
    timestamp: datetime
    status: StatusPonto
    local_ponto_id: UUID | None = None
    local_ponto_nome: str | None = None
    fora_local_autorizado: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    gps_accuracy_meters: float | None = None


class RhFeriasCreateRequest(BaseModel):
    funcionario_id: UUID | None = None
    data_inicio: datetime
    data_fim: datetime


class RhFeriasResponse(BaseModel):
    id: UUID
    funcionario_id: UUID
    data_inicio: datetime
    data_fim: datetime
    status: StatusFerias
    motivo_rejeicao: str | None = None


class RhAjustePontoCreateRequest(BaseModel):
    funcionario_id: UUID | None = None
    data_referencia: datetime
    justificativa: str
    hora_entrada_solicitada: datetime | None = None
    hora_saida_solicitada: datetime | None = None


class RhAjustePontoResponse(BaseModel):
    id: UUID
    funcionario_id: UUID
    data_referencia: datetime
    justificativa: str
    hora_entrada_solicitada: datetime | None = None
    hora_saida_solicitada: datetime | None = None
    status: StatusAjuste
    motivo_rejeicao: str | None = None


class RhMotivoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str


class RhTipoAtestadoCreateRequest(BaseModel):
    nome: str
    prazo_entrega_dias: int
    abona_falta: bool = True
    descricao: str | None = None


class RhTipoAtestadoUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    prazo_entrega_dias: int | None = None
    abona_falta: bool | None = None
    descricao: str | None = None


class RhTipoAtestadoResponse(BaseModel):
    id: UUID
    nome: str
    prazo_entrega_dias: int
    abona_falta: bool
    descricao: str | None = None


class RhAtestadoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funcionario_id: UUID | None = None
    tipo_atestado_id: UUID
    data_inicio: datetime
    data_fim: datetime


class RhAtestadoEntregarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str | None = None


class RhAtestadoUploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str
    content_type: str
    size_bytes: int


class RhAtestadoUploadUrlResponse(BaseModel):
    upload_url: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)


class RhAtestadoConfirmarUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    content_type: str
    size_bytes: int


class RhAtestadoResponse(BaseModel):
    id: UUID
    funcionario_id: UUID
    tipo_atestado_id: UUID
    data_inicio: datetime
    data_fim: datetime
    status: StatusAtestado
    motivo_rejeicao: str | None = None
    has_file: bool


class RhAtestadoDownloadUrlResponse(BaseModel):
    download_url: str
    expires_in: int


class RhFolhaGerarRequest(BaseModel):
    mes: int
    ano: int
    funcionario_id: UUID | None = None


class RhHoleriteAjustesRequest(BaseModel):
    acrescimos_manuais: Decimal
    descontos_manuais: Decimal
    motivo: str


class RhHoleriteResponse(BaseModel):
    id: UUID
    funcionario_id: UUID
    mes_referencia: int
    ano_referencia: int
    salario_base: Decimal
    horas_extras: Decimal
    descontos_falta: Decimal
    acrescimos_manuais: Decimal
    descontos_manuais: Decimal
    valor_liquido: Decimal
    status: StatusHolerite
    pagamento_agendado_id: UUID | None = None
    valor_bruto: Decimal = Decimal("0.00")
    total_proventos: Decimal = Decimal("0.00")
    total_descontos: Decimal = Decimal("0.00")
    total_informativos: Decimal = Decimal("0.00")
    calculation_version: str | None = None
    calculation_hash: str | None = None
    calculated_at: datetime | None = None


class RhFecharFolhaRequest(BaseModel):
    mes: int
    ano: int
    funcionario_ids: list[UUID] | None = None


class RhFolhaJobCreateRequest(BaseModel):
    mes: int
    ano: int
    funcionario_ids: list[UUID] | None = None


class RhFolhaJobResponse(BaseModel):
    id: UUID
    mes: int
    ano: int
    status: RhFolhaJobStatus
    total_funcionarios: int
    processados: int
    falhas: int
    error_summary: list[dict] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class RhAplicabilidadeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    escopo: EscopoAplicabilidade
    valor: str | None = None


class RhAplicabilidadeResponse(BaseModel):
    id: UUID | None = None
    escopo: EscopoAplicabilidade
    valor: str | None = None


class RhBeneficioCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str
    descricao: str | None = None


class RhBeneficioUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    descricao: str | None = None


class RhBeneficioResponse(BaseModel):
    id: UUID
    nome: str
    descricao: str | None = None
    status: StatusBeneficio


class RhRegraEncargoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nome: str
    tipo_calculo: TipoRegraEncargo
    natureza: NaturezaEncargo
    base_calculo: BaseCalculoEncargo
    prioridade: int = 100
    descricao: str | None = None
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None
    valor_fixo: Decimal | None = None
    percentual: Decimal | None = None
    tabela_progressiva_id: UUID | None = None
    teto: Decimal | None = None
    piso: Decimal | None = None
    arredondamento: str = "ROUND_HALF_UP"
    incide_no_liquido: bool = True
    aplicabilidades: list[RhAplicabilidadeRequest] = Field(default_factory=list)


class RhRegraEncargoUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str | None = None
    nome: str | None = None
    tipo_calculo: TipoRegraEncargo | None = None
    natureza: NaturezaEncargo | None = None
    base_calculo: BaseCalculoEncargo | None = None
    prioridade: int | None = None
    descricao: str | None = None
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None
    valor_fixo: Decimal | None = None
    percentual: Decimal | None = None
    tabela_progressiva_id: UUID | None = None
    teto: Decimal | None = None
    piso: Decimal | None = None
    arredondamento: str | None = None
    incide_no_liquido: bool | None = None
    aplicabilidades: list[RhAplicabilidadeRequest] | None = None


class RhRegraEncargoNovaVersaoRequest(RhRegraEncargoUpdateRequest):
    pass


class RhRegraEncargoResponse(BaseModel):
    id: UUID
    regra_grupo_id: UUID
    codigo: str
    nome: str
    descricao: str | None = None
    tipo_calculo: TipoRegraEncargo
    natureza: NaturezaEncargo
    base_calculo: BaseCalculoEncargo
    prioridade: int
    status: StatusRegraEncargo
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None
    valor_fixo: Decimal | None = None
    percentual: Decimal | None = None
    tabela_progressiva_id: UUID | None = None
    tabela_progressiva_nome: str | None = None
    teto: Decimal | None = None
    piso: Decimal | None = None
    arredondamento: str
    incide_no_liquido: bool
    aplicabilidades: list[RhAplicabilidadeResponse] = Field(default_factory=list)


class RhRegraEncargoListItem(RhRegraEncargoResponse):
    pass


class RhFaixaEncargoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordem: int
    valor_inicial: Decimal
    valor_final: Decimal | None = None
    aliquota: Decimal
    deducao: Decimal = Decimal("0.00")
    calculo_marginal: bool = False


class RhFaixaEncargoResponse(BaseModel):
    id: UUID | None = None
    ordem: int
    valor_inicial: Decimal
    valor_final: Decimal | None = None
    aliquota: Decimal
    deducao: Decimal
    calculo_marginal: bool


class RhTabelaProgressivaCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nome: str
    descricao: str | None = None
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None


class RhTabelaProgressivaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str | None = None
    nome: str | None = None
    descricao: str | None = None
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None


class RhTabelaProgressivaFaixasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faixas: list[RhFaixaEncargoRequest]


class RhTabelaProgressivaResponse(BaseModel):
    id: UUID
    codigo: str
    nome: str
    descricao: str | None = None
    status: StatusRegraEncargo
    vigencia_inicio: datetime | None = None
    vigencia_fim: datetime | None = None
    faixas: list[RhFaixaEncargoResponse] = Field(default_factory=list)


class RhHoleriteItemResponse(BaseModel):
    id: UUID
    holerite_id: UUID
    funcionario_id: UUID
    tipo: HoleriteItemTipo
    origem: str
    codigo: str
    descricao: str
    natureza: HoleriteItemNatureza
    ordem: int
    base: Decimal
    valor: Decimal
    regra_encargo_id: UUID | None = None
    regra_grupo_id: UUID | None = None
    regra_nome: str | None = None
    regra_versao: str | None = None
    is_automatico: bool


class RhHoleriteSnapshotResponse(BaseModel):
    item_id: UUID | str
    codigo: str
    descricao: str
    snapshot_regra: dict | str | None = None
    snapshot_calculo: dict | str | None = None


class RhPontoDiaDetalheResponse(BaseModel):
    funcionario_id: UUID
    funcionario_nome: str
    funcionario_cpf_mascarado: str
    funcionario_cargo: str
    status: str
    local_autorizado_nome: str | None = None
    registros: list[RhRegistroPontoListItem] = Field(default_factory=list)
    locais_autorizados: list[RhLocalPontoResponse] = Field(default_factory=list)
    ajustes_relacionados: list[dict] = Field(default_factory=list)
    impacto_estimado: dict
    auditoria_resumida: list[dict] = Field(default_factory=list)


class RhDashboardSummaryResponse(BaseModel):
    mes: int
    ano: int
    total_funcionarios_ativos: int
    ajustes_pendentes: int
    ferias_em_andamento: int
    atestados_aguardando: int
    atestados_vencidos: int
    pontos_negados_periodo: int
    pontos_inconsistentes_periodo: int
    holerites_rascunho: int
    holerites_fechados: int
    total_liquido_competencia: Decimal


class RhUltimoPontoResumoResponse(BaseModel):
    tipo: TipoPonto
    status: StatusPonto
    timestamp: datetime


class RhUltimoHoleriteResumoResponse(BaseModel):
    mes_referencia: int
    ano_referencia: int
    valor_liquido: Decimal
    status: StatusHolerite


class RhMeResumoResponse(BaseModel):
    ultimo_ponto: RhUltimoPontoResumoResponse | None = None
    ajustes_pendentes: int
    ferias_pendentes: int
    atestados_pendentes: int
    ultimo_holerite_fechado: RhUltimoHoleriteResumoResponse | None = None


class RhAuditLogResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID | None = None
    action: str
    actor_user_id: UUID | None = None
    actor_role: str
    reason: str | None = None
    before: dict | None = None
    after: dict | None = None
    request_id: str | None = None
    ip_hash: str | None = None
    user_agent: str | None = None
    created_at: datetime
