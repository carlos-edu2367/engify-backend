from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.rh import StatusAjuste, StatusAtestado, StatusFerias, StatusHolerite, StatusPonto, TipoPonto


class IntervaloHorarioDTO(BaseModel):
    hora_inicio: time
    hora_fim: time


class TurnoHorarioDTO(BaseModel):
    dia_semana: int
    hora_entrada: time
    hora_saida: time
    intervalos: list[IntervaloHorarioDTO] = Field(default_factory=list)


class CreateFuncionarioDTO(BaseModel):
    nome: str
    cpf: str
    cargo: str
    salario_base: Decimal
    data_admissao: date
    user_id: UUID | None = None
    horario_trabalho: list[TurnoHorarioDTO] = Field(min_length=1)


class UpdateFuncionarioDTO(BaseModel):
    nome: Optional[str] = None
    cpf: Optional[str] = None
    cargo: Optional[str] = None
    salario_base: Optional[Decimal] = None
    data_admissao: Optional[date] = None
    user_id: UUID | None = None
    is_active: Optional[bool] = None
    reason: Optional[str] = None


class ReplaceHorarioTrabalhoDTO(BaseModel):
    turnos: list[TurnoHorarioDTO] = Field(min_length=1)


class CreateLocalPontoDTO(BaseModel):
    nome: str
    latitude: float
    longitude: float
    raio_metros: float = Field(default=100, ge=20, le=1000)


class UpdateLocalPontoDTO(BaseModel):
    nome: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    raio_metros: Optional[float] = Field(default=None, ge=20, le=1000)


class RegistrarPontoDTO(BaseModel):
    tipo: TipoPonto
    latitude: float
    longitude: float
    client_timestamp: datetime | None = None
    gps_accuracy_meters: float | None = None
    device_fingerprint: str | None = None


class CreateFeriasDTO(BaseModel):
    funcionario_id: UUID | None = None
    data_inicio: datetime
    data_fim: datetime


class FeriasFiltersDTO(BaseModel):
    funcionario_id: UUID | None = None
    status: StatusFerias | None = None
    start: datetime | None = None
    end: datetime | None = None


class CreateAjustePontoDTO(BaseModel):
    funcionario_id: UUID | None = None
    data_referencia: datetime
    justificativa: str
    hora_entrada_solicitada: datetime | None = None
    hora_saida_solicitada: datetime | None = None


class AjustePontoFiltersDTO(BaseModel):
    funcionario_id: UUID | None = None
    status: StatusAjuste | None = None
    start: datetime | None = None
    end: datetime | None = None


class CreateTipoAtestadoDTO(BaseModel):
    nome: str
    prazo_entrega_dias: int
    abona_falta: bool = True
    descricao: str | None = None


class UpdateTipoAtestadoDTO(BaseModel):
    nome: Optional[str] = None
    prazo_entrega_dias: Optional[int] = None
    abona_falta: Optional[bool] = None
    descricao: Optional[str] = None


class CreateAtestadoDTO(BaseModel):
    funcionario_id: UUID | None = None
    tipo_atestado_id: UUID
    data_inicio: datetime
    data_fim: datetime
    file_path: str | None = None


class AtestadoFiltersDTO(BaseModel):
    funcionario_id: UUID | None = None
    tipo_atestado_id: UUID | None = None
    status: StatusAtestado | None = None
    start: datetime | None = None
    end: datetime | None = None


class HoleriteFiltersDTO(BaseModel):
    funcionario_id: UUID | None = None
    mes: int
    ano: int
    status: StatusHolerite | None = None


class UpdateHoleriteAjustesDTO(BaseModel):
    acrescimos_manuais: Decimal
    descontos_manuais: Decimal
    motivo: str


class RhDashboardSummaryDTO(BaseModel):
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


class RhUltimoPontoDTO(BaseModel):
    tipo: TipoPonto
    status: StatusPonto
    timestamp: datetime


class RhUltimoHoleriteFechadoDTO(BaseModel):
    mes_referencia: int
    ano_referencia: int
    valor_liquido: Decimal
    status: StatusHolerite


class RhMeResumoDTO(BaseModel):
    ultimo_ponto: RhUltimoPontoDTO | None = None
    ajustes_pendentes: int
    ferias_pendentes: int
    atestados_pendentes: int
    ultimo_holerite_fechado: RhUltimoHoleriteFechadoDTO | None = None


class RhAuditLogFiltersDTO(BaseModel):
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor_user_id: UUID | None = None
    action: str | None = None
    start: datetime | None = None
    end: datetime | None = None


class RhAuditLogListItemDTO(BaseModel):
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
