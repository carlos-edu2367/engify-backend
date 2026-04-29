from dataclasses import dataclass, field
from datetime import datetime, timezone
from datetime import time as Time
from enum import Enum
from uuid import UUID, uuid4

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.errors import DomainError


@dataclass
class IntervaloHorario:
    hora_inicio: Time
    hora_fim: Time

    def __post_init__(self) -> None:
        if self.hora_fim <= self.hora_inicio:
            raise DomainError("Hora de fim do intervalo deve ser posterior a hora de inicio")

    @property
    def minutos(self) -> int:
        return _time_to_minutes(self.hora_fim) - _time_to_minutes(self.hora_inicio)


@dataclass
class TurnoHorario:
    dia_semana: int
    hora_entrada: Time
    hora_saida: Time
    intervalos: list[IntervaloHorario] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.dia_semana < 0 or self.dia_semana > 6:
            raise DomainError("Dia da semana invalido")
        if self.hora_saida <= self.hora_entrada:
            raise DomainError("Hora de saida deve ser posterior a hora de entrada")
        self._validate_intervalos()

    @property
    def horas_esperadas(self) -> float:
        entrada = _time_to_minutes(self.hora_entrada)
        saida = _time_to_minutes(self.hora_saida)
        intervalo_minutos = sum(intervalo.minutos for intervalo in self.intervalos)
        return (saida - entrada - intervalo_minutos) / 60

    def _validate_intervalos(self) -> None:
        entrada = _time_to_minutes(self.hora_entrada)
        saida = _time_to_minutes(self.hora_saida)
        ordered = sorted(self.intervalos, key=lambda intervalo: intervalo.hora_inicio)
        previous_end: int | None = None
        for intervalo in ordered:
            inicio = _time_to_minutes(intervalo.hora_inicio)
            fim = _time_to_minutes(intervalo.hora_fim)
            if inicio < entrada or fim > saida:
                raise DomainError("Intervalo deve estar dentro do turno")
            if previous_end is not None and inicio < previous_end:
                raise DomainError("Intervalos do turno nao podem se sobrepor")
            previous_end = fim


def _time_to_minutes(value: Time) -> int:
    return value.hour * 60 + value.minute


class HorarioTrabalho:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        turnos: list[TurnoHorario],
        id: UUID | None = None,
    ) -> None:
        if not turnos:
            raise DomainError("Horario de trabalho deve ter ao menos um turno")
        dias = [turno.dia_semana for turno in turnos]
        if len(dias) != len(set(dias)):
            raise DomainError("Nao pode haver dois turnos para o mesmo dia da semana")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.turnos = turnos
        self.is_deleted = False

    def turno_para_dia(self, dia_semana: int) -> TurnoHorario | None:
        return next((turno for turno in self.turnos if turno.dia_semana == dia_semana), None)

    def delete(self) -> None:
        self.is_deleted = True


class Funcionario:
    def __init__(
        self,
        team_id: UUID,
        nome: str,
        cpf: CPF,
        cargo: str,
        salario_base: Money,
        data_admissao: datetime,
        user_id: UUID | None = None,
        is_active: bool = True,
        id: UUID | None = None,
    ) -> None:
        if not nome.strip():
            raise DomainError("Nome do funcionario e obrigatorio")
        if not cargo.strip():
            raise DomainError("Cargo do funcionario e obrigatorio")
        if salario_base.amount < 0:
            raise DomainError("Salario base nao pode ser negativo")
        self.id = id or uuid4()
        self.team_id = team_id
        self.nome = nome
        self.cpf = cpf
        self.cargo = cargo
        self.salario_base = salario_base
        self.data_admissao = data_admissao
        self.user_id = user_id
        self.is_active = is_active
        self.is_deleted = False
        self.horario_trabalho: HorarioTrabalho | None = None

    def delete(self) -> None:
        self.is_deleted = True

    def desativar(self) -> None:
        self.is_active = False


class StatusFerias(Enum):
    SOLICITADO = "solicitado"
    APROVADO = "aprovado"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"
    REJEITADO = "rejeitado"


class Ferias:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        data_inicio: datetime,
        data_fim: datetime,
        status: StatusFerias = StatusFerias.SOLICITADO,
        motivo_rejeicao: str | None = None,
        id: UUID | None = None,
    ) -> None:
        if data_fim <= data_inicio:
            raise DomainError("Data de fim deve ser posterior a data de inicio")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.status = status
        self.motivo_rejeicao = motivo_rejeicao
        self.is_deleted = False

    def aprovar(self) -> None:
        if self.status != StatusFerias.SOLICITADO:
            raise DomainError("Ferias somente podem ser aprovadas quando solicitadas")
        self.status = StatusFerias.APROVADO

    def rejeitar(self, motivo: str) -> None:
        if self.status != StatusFerias.SOLICITADO:
            raise DomainError("Ferias somente podem ser rejeitadas quando solicitadas")
        if not motivo.strip():
            raise DomainError("Motivo de rejeicao e obrigatorio")
        self.status = StatusFerias.REJEITADO
        self.motivo_rejeicao = motivo

    def cancelar(self, motivo: str) -> None:
        if self.status not in {StatusFerias.SOLICITADO, StatusFerias.APROVADO, StatusFerias.EM_ANDAMENTO}:
            raise DomainError("Ferias nao podem ser canceladas neste status")
        if not motivo.strip():
            raise DomainError("Motivo de cancelamento e obrigatorio")
        self.status = StatusFerias.CANCELADO
        self.motivo_rejeicao = motivo

    def delete(self) -> None:
        self.is_deleted = True


class LocalPonto:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        nome: str,
        latitude: float,
        longitude: float,
        raio_metros: float = 100.0,
        id: UUID | None = None,
    ) -> None:
        if not nome.strip():
            raise DomainError("Nome do local e obrigatorio")
        if latitude < -90 or latitude > 90:
            raise DomainError("Latitude invalida")
        if longitude < -180 or longitude > 180:
            raise DomainError("Longitude invalida")
        if raio_metros <= 0:
            raise DomainError("Raio deve ser positivo")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.nome = nome
        self.latitude = latitude
        self.longitude = longitude
        self.raio_metros = raio_metros
        self.is_deleted = False

    def delete(self) -> None:
        self.is_deleted = True


class TipoPonto(Enum):
    ENTRADA = "entrada"
    SAIDA = "saida"


class StatusPonto(Enum):
    VALIDADO = "validado"
    NEGADO = "negado"
    INCONSISTENTE = "inconsistente"
    AJUSTADO = "ajustado"


class RegistroPonto:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        tipo: TipoPonto,
        timestamp: datetime,
        latitude: float,
        longitude: float,
        status: StatusPonto = StatusPonto.VALIDADO,
        local_ponto_id: UUID | None = None,
        client_timestamp: datetime | None = None,
        gps_accuracy_meters: float | None = None,
        device_fingerprint: str | None = None,
        ip_hash: str | None = None,
        denial_reason: str | None = None,
        id: UUID | None = None,
    ) -> None:
        if latitude < -90 or latitude > 90:
            raise DomainError("Latitude invalida")
        if longitude < -180 or longitude > 180:
            raise DomainError("Longitude invalida")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.tipo = tipo
        self.timestamp = timestamp
        self.latitude = latitude
        self.longitude = longitude
        self.status = status
        self.local_ponto_id = local_ponto_id
        self.client_timestamp = client_timestamp
        self.gps_accuracy_meters = gps_accuracy_meters
        self.device_fingerprint = device_fingerprint
        self.ip_hash = ip_hash
        self.denial_reason = denial_reason
        self.is_deleted = False

    def marcar_ajustado(self) -> None:
        self.status = StatusPonto.AJUSTADO

    def delete(self) -> None:
        self.is_deleted = True


class StatusAjuste(Enum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"


class AjustePonto:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        data_referencia: datetime,
        justificativa: str,
        hora_entrada_solicitada: datetime | None = None,
        hora_saida_solicitada: datetime | None = None,
        status: StatusAjuste = StatusAjuste.PENDENTE,
        motivo_rejeicao: str | None = None,
        id: UUID | None = None,
    ) -> None:
        if not justificativa.strip():
            raise DomainError("Justificativa do ajuste e obrigatoria")
        if hora_entrada_solicitada is None and hora_saida_solicitada is None:
            raise DomainError("Informe ao menos um horario solicitado")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.data_referencia = data_referencia
        self.justificativa = justificativa
        self.hora_entrada_solicitada = hora_entrada_solicitada
        self.hora_saida_solicitada = hora_saida_solicitada
        self.status = status
        self.motivo_rejeicao = motivo_rejeicao
        self.created_at = datetime.now(timezone.utc)
        self.is_deleted = False

    def aprovar(self) -> None:
        if self.status != StatusAjuste.PENDENTE:
            raise DomainError("Ajuste somente pode ser aprovado quando pendente")
        self.status = StatusAjuste.APROVADO

    def rejeitar(self, motivo: str) -> None:
        if self.status != StatusAjuste.PENDENTE:
            raise DomainError("Ajuste somente pode ser rejeitado quando pendente")
        if not motivo.strip():
            raise DomainError("Motivo de rejeicao e obrigatorio")
        self.status = StatusAjuste.REJEITADO
        self.motivo_rejeicao = motivo

    def delete(self) -> None:
        self.is_deleted = True


class TipoAtestado:
    def __init__(
        self,
        team_id: UUID,
        nome: str,
        prazo_entrega_dias: int,
        abona_falta: bool = True,
        descricao: str | None = None,
        id: UUID | None = None,
    ) -> None:
        if not nome.strip():
            raise DomainError("Nome do tipo de atestado e obrigatorio")
        if prazo_entrega_dias < 0:
            raise DomainError("Prazo de entrega nao pode ser negativo")
        self.id = id or uuid4()
        self.team_id = team_id
        self.nome = nome
        self.prazo_entrega_dias = prazo_entrega_dias
        self.abona_falta = abona_falta
        self.descricao = descricao
        self.is_deleted = False

    def delete(self) -> None:
        self.is_deleted = True


class StatusAtestado(Enum):
    AGUARDANDO_ENTREGA = "aguardando_entrega"
    ENTREGUE = "entregue"
    VENCIDO = "vencido"
    REJEITADO = "rejeitado"


class Atestado:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        tipo_atestado_id: UUID,
        data_inicio: datetime,
        data_fim: datetime,
        file_path: str | None = None,
        status: StatusAtestado = StatusAtestado.AGUARDANDO_ENTREGA,
        motivo_rejeicao: str | None = None,
        id: UUID | None = None,
    ) -> None:
        if data_fim < data_inicio:
            raise DomainError("Data de fim do atestado nao pode ser anterior ao inicio")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.tipo_atestado_id = tipo_atestado_id
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.file_path = file_path
        self.status = status
        self.motivo_rejeicao = motivo_rejeicao
        self.created_at = datetime.now(timezone.utc)
        self.is_deleted = False

    def entregar(self) -> None:
        if self.status != StatusAtestado.AGUARDANDO_ENTREGA:
            raise DomainError("Atestado somente pode ser entregue quando aguardando entrega")
        self.status = StatusAtestado.ENTREGUE

    def rejeitar(self, motivo: str) -> None:
        if self.status not in {StatusAtestado.AGUARDANDO_ENTREGA, StatusAtestado.ENTREGUE}:
            raise DomainError("Atestado nao pode ser rejeitado neste status")
        if not motivo.strip():
            raise DomainError("Motivo de rejeicao e obrigatorio")
        self.status = StatusAtestado.REJEITADO
        self.motivo_rejeicao = motivo

    def vencer(self) -> None:
        if self.status != StatusAtestado.AGUARDANDO_ENTREGA:
            raise DomainError("Atestado somente pode vencer quando aguardando entrega")
        self.status = StatusAtestado.VENCIDO

    def delete(self) -> None:
        self.is_deleted = True


class StatusHolerite(Enum):
    RASCUNHO = "rascunho"
    FECHADO = "fechado"
    CANCELADO = "cancelado"


class Holerite:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        mes_referencia: int,
        ano_referencia: int,
        salario_base: Money,
        horas_extras: Money,
        descontos_falta: Money,
        acrescimos_manuais: Money,
        descontos_manuais: Money,
        valor_liquido: Money,
        status: StatusHolerite = StatusHolerite.RASCUNHO,
        pagamento_agendado_id: UUID | None = None,
        id: UUID | None = None,
    ) -> None:
        if mes_referencia < 1 or mes_referencia > 12:
            raise DomainError("Mes de referencia invalido")
        if ano_referencia <= 0:
            raise DomainError("Ano de referencia invalido")
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.mes_referencia = mes_referencia
        self.ano_referencia = ano_referencia
        self.salario_base = salario_base
        self.horas_extras = horas_extras
        self.descontos_falta = descontos_falta
        self.acrescimos_manuais = acrescimos_manuais
        self.descontos_manuais = descontos_manuais
        self.valor_liquido = valor_liquido
        self.status = status
        self.pagamento_agendado_id = pagamento_agendado_id
        self.is_deleted = False
        self.recalcular_valor_liquido()

    def recalcular_valor_liquido(self) -> None:
        self.valor_liquido = (
            self.salario_base
            + self.horas_extras
            + self.acrescimos_manuais
            - self.descontos_falta
            - self.descontos_manuais
        )

    def atualizar_ajustes_manuais(
        self,
        acrescimos_manuais: Money,
        descontos_manuais: Money,
    ) -> None:
        if self.status != StatusHolerite.RASCUNHO:
            raise DomainError("Ajustes manuais so podem ser alterados em holerite rascunho")
        if acrescimos_manuais.amount < 0 or descontos_manuais.amount < 0:
            raise DomainError("Ajustes manuais nao podem ser negativos")
        self.acrescimos_manuais = acrescimos_manuais
        self.descontos_manuais = descontos_manuais
        self.recalcular_valor_liquido()

    def fechar(self, pagamento_id: UUID) -> None:
        if self.status != StatusHolerite.RASCUNHO:
            raise DomainError("Holerite so pode ser fechado a partir de rascunho")
        self.status = StatusHolerite.FECHADO
        self.pagamento_agendado_id = pagamento_id

    def delete(self) -> None:
        self.is_deleted = True


class RhAuditLog:
    def __init__(
        self,
        team_id: UUID,
        actor_user_id: UUID | None,
        actor_role: str,
        entity_type: str,
        entity_id: UUID | None,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
        request_id: str | None = None,
        ip_hash: str | None = None,
        user_agent: str | None = None,
        created_at: datetime | None = None,
        id: UUID | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.team_id = team_id
        self.actor_user_id = actor_user_id
        self.actor_role = actor_role
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.action = action
        self.before = before
        self.after = after
        self.reason = reason
        self.request_id = request_id
        self.ip_hash = ip_hash
        self.user_agent = user_agent
        self.created_at = created_at or datetime.now(timezone.utc)


class RhIdempotencyKey:
    def __init__(
        self,
        team_id: UUID,
        scope: str,
        key: str,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.team_id = team_id
        self.scope = scope
        self.key = key
        self.created_at = created_at or datetime.now(timezone.utc)


class RhSalarioHistorico:
    def __init__(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        salario_anterior: Money,
        salario_novo: Money,
        changed_by_user_id: UUID | None = None,
        reason: str | None = None,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.team_id = team_id
        self.funcionario_id = funcionario_id
        self.salario_anterior = salario_anterior
        self.salario_novo = salario_novo
        self.changed_by_user_id = changed_by_user_id
        self.reason = reason
        self.created_at = created_at or datetime.now(timezone.utc)
