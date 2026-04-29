from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.rh import StatusAjuste, StatusAtestado, StatusFerias, StatusHolerite, StatusPonto, TipoPonto


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


class RhFuncionarioResponse(BaseModel):
    id: UUID
    nome: str
    cpf: str
    cpf_mascarado: str
    cargo: str
    salario_base: Decimal
    data_admissao: date
    user_id: UUID | None = None
    is_active: bool
    horario_trabalho: RhHorarioTrabalhoResponse | None = None


class RhLocalPontoCreateRequest(BaseModel):
    nome: str
    latitude: float
    longitude: float
    raio_metros: float = Field(default=100)


class RhLocalPontoUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    raio_metros: float | None = None


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
    funcionario_id: UUID | None = None
    tipo_atestado_id: UUID
    data_inicio: datetime
    data_fim: datetime
    file_path: str | None = None


class RhAtestadoEntregarRequest(BaseModel):
    file_path: str | None = None


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


class RhFecharFolhaRequest(BaseModel):
    mes: int
    ano: int
    funcionario_ids: list[UUID] | None = None


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
