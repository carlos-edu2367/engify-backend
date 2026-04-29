from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from datetime import time as Time
from decimal import Decimal
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


class TipoRegraEncargo(Enum):
    VALOR_FIXO = "valor_fixo"
    PERCENTUAL_SIMPLES = "percentual_simples"
    TABELA_PROGRESSIVA = "tabela_progressiva"


class NaturezaEncargo(Enum):
    PROVENTO = "provento"
    DESCONTO = "desconto"
    INFORMATIVO = "informativo"


class BaseCalculoEncargo(Enum):
    SALARIO_BASE = "salario_base"
    SALARIO_BASE_MAIS_EXTRAS = "salario_base_mais_extras"
    BRUTO_ANTES_ENCARGOS = "bruto_antes_encargos"
    BRUTO_ANTES_IRRF = "bruto_antes_irrf"
    LIQUIDO_PARCIAL = "liquido_parcial"
    VALOR_REFERENCIA_MANUAL = "valor_referencia_manual"


class EscopoAplicabilidade(Enum):
    TODOS_FUNCIONARIOS = "todos_funcionarios"
    POR_CARGO = "por_cargo"
    POR_FUNCIONARIO = "por_funcionario"
    POR_TIPO_CONTRATO = "por_tipo_contrato"
    POR_EMPRESA = "por_empresa"
    POR_TAG = "por_tag"


class StatusRegraEncargo(Enum):
    RASCUNHO = "rascunho"
    ATIVA = "ativa"
    INATIVA = "inativa"
    ARQUIVADA = "arquivada"


class HoleriteItemTipo(Enum):
    SALARIO_BASE = "salario_base"
    HORA_EXTRA = "hora_extra"
    FALTA = "falta"
    AJUSTE_MANUAL = "ajuste_manual"
    ENCARGO_AUTOMATICO = "encargo_automatico"
    BENEFICIO_AUTOMATICO = "beneficio_automatico"
    INFORMATIVO = "informativo"


class HoleriteItemNatureza(Enum):
    PROVENTO = "provento"
    DESCONTO = "desconto"
    INFORMATIVO = "informativo"


class FaixaEncargo:
    def __init__(
        self,
        team_id: UUID,
        valor_inicial: Money,
        aliquota: Decimal,
        ordem: int,
        valor_final: Money | None = None,
        deducao: Money | None = None,
        calculo_marginal: bool = False,
        id: UUID | None = None,
    ) -> None:
        if ordem < 0:
            raise DomainError("Ordem da faixa deve ser positiva")
        if aliquota < 0:
            raise DomainError("Aliquota da faixa nao pode ser negativa")
        if valor_final is not None and valor_final.amount < valor_inicial.amount:
            raise DomainError("Valor final da faixa nao pode ser menor que o valor inicial")
        self.id = id or uuid4()
        self.team_id = team_id
        self.valor_inicial = valor_inicial
        self.valor_final = valor_final
        self.aliquota = Decimal(str(aliquota))
        self.deducao = deducao or Money(Decimal("0.00"))
        self.ordem = ordem
        self.calculo_marginal = calculo_marginal


class TabelaProgressiva:
    def __init__(
        self,
        team_id: UUID,
        codigo: str,
        nome: str,
        status: StatusRegraEncargo = StatusRegraEncargo.RASCUNHO,
        vigencia_inicio: datetime | None = None,
        vigencia_fim: datetime | None = None,
        descricao: str | None = None,
        faixas: list[FaixaEncargo] | None = None,
        created_by_user_id: UUID | None = None,
        approved_by_user_id: UUID | None = None,
        id: UUID | None = None,
    ) -> None:
        if not codigo.strip():
            raise DomainError("Codigo da tabela progressiva e obrigatorio")
        if not nome.strip():
            raise DomainError("Nome da tabela progressiva e obrigatorio")
        if vigencia_inicio and vigencia_fim and vigencia_fim < vigencia_inicio:
            raise DomainError("Vigencia final nao pode ser anterior a vigencia inicial")
        self.id = id or uuid4()
        self.team_id = team_id
        self.codigo = codigo
        self.nome = nome
        self.status = status
        self.vigencia_inicio = vigencia_inicio
        self.vigencia_fim = vigencia_fim
        self.descricao = descricao
        self.faixas = list(faixas or [])
        self.created_by_user_id = created_by_user_id
        self.approved_by_user_id = approved_by_user_id
        self.is_deleted = False
        self._validate_faixas()
        if self.status == StatusRegraEncargo.ATIVA:
            if self.vigencia_inicio is None:
                raise DomainError("Tabela progressiva ativa exige vigencia inicial")
            if not self.faixas:
                raise DomainError("Tabela progressiva ativa exige ao menos uma faixa")

    def _validate_faixas(self) -> None:
        ordered = sorted(self.faixas, key=lambda faixa: faixa.ordem)
        previous_end: Decimal | None = None
        for faixa in ordered:
            start = faixa.valor_inicial.amount
            end = faixa.valor_final.amount if faixa.valor_final is not None else None
            if previous_end is not None and start < previous_end:
                raise DomainError("Faixas progressivas nao podem se sobrepor")
            previous_end = end if end is not None else previous_end


class RegraEncargoAplicabilidade:
    def __init__(
        self,
        team_id: UUID,
        escopo: EscopoAplicabilidade,
        valor: str | None = None,
        id: UUID | None = None,
    ) -> None:
        if escopo != EscopoAplicabilidade.TODOS_FUNCIONARIOS and not (valor or "").strip():
            raise DomainError("Valor da aplicabilidade e obrigatorio para este escopo")
        self.id = id or uuid4()
        self.team_id = team_id
        self.escopo = escopo
        self.valor = valor


class RegraEncargo:
    def __init__(
        self,
        team_id: UUID,
        codigo: str,
        nome: str,
        tipo_calculo: TipoRegraEncargo,
        natureza: NaturezaEncargo,
        base_calculo: BaseCalculoEncargo,
        prioridade: int,
        status: StatusRegraEncargo = StatusRegraEncargo.RASCUNHO,
        descricao: str | None = None,
        vigencia_inicio: datetime | None = None,
        vigencia_fim: datetime | None = None,
        valor_fixo: Money | None = None,
        percentual: Decimal | None = None,
        tabela_progressiva_id: UUID | None = None,
        teto: Money | None = None,
        piso: Money | None = None,
        arredondamento: str = "ROUND_HALF_UP",
        incide_no_liquido: bool = True,
        is_system: bool = False,
        regra_grupo_id: UUID | None = None,
        created_by_user_id: UUID | None = None,
        updated_by_user_id: UUID | None = None,
        approved_by_user_id: UUID | None = None,
        aplicabilidades: list[RegraEncargoAplicabilidade] | None = None,
        tabela_progressiva: TabelaProgressiva | None = None,
        id: UUID | None = None,
    ) -> None:
        if not codigo.strip():
            raise DomainError("Codigo da regra e obrigatorio")
        if not nome.strip():
            raise DomainError("Nome da regra e obrigatorio")
        if prioridade < 0:
            raise DomainError("Prioridade da regra nao pode ser negativa")
        if vigencia_inicio and vigencia_fim and vigencia_fim < vigencia_inicio:
            raise DomainError("Vigencia final nao pode ser anterior a vigencia inicial")
        if tipo_calculo == TipoRegraEncargo.VALOR_FIXO and valor_fixo is None:
            raise DomainError("Regra de valor fixo exige valor_fixo")
        if tipo_calculo == TipoRegraEncargo.PERCENTUAL_SIMPLES:
            if percentual is None:
                raise DomainError("Regra percentual exige percentual")
            if Decimal(str(percentual)) < 0:
                raise DomainError("Percentual da regra nao pode ser negativo")
        if tipo_calculo == TipoRegraEncargo.TABELA_PROGRESSIVA and tabela_progressiva_id is None:
            raise DomainError("Regra progressiva exige tabela progressiva")
        if status == StatusRegraEncargo.ATIVA and vigencia_inicio is None:
            raise DomainError("Regra ativa exige vigencia inicial")
        self.id = id or uuid4()
        self.regra_grupo_id = regra_grupo_id or uuid4()
        self.team_id = team_id
        self.codigo = codigo
        self.nome = nome
        self.tipo_calculo = tipo_calculo
        self.natureza = natureza
        self.base_calculo = base_calculo
        self.prioridade = prioridade
        self.status = status
        self.descricao = descricao
        self.vigencia_inicio = vigencia_inicio
        self.vigencia_fim = vigencia_fim
        self.valor_fixo = valor_fixo
        self.percentual = Decimal(str(percentual)) if percentual is not None else None
        self.tabela_progressiva_id = tabela_progressiva_id
        self.teto = teto
        self.piso = piso
        self.arredondamento = arredondamento
        self.incide_no_liquido = incide_no_liquido
        self.is_system = is_system
        self.created_by_user_id = created_by_user_id
        self.updated_by_user_id = updated_by_user_id
        self.approved_by_user_id = approved_by_user_id
        self.aplicabilidades = list(aplicabilidades or [])
        self.tabela_progressiva = tabela_progressiva
        self.is_deleted = False


class HoleriteItem:
    def __init__(
        self,
        team_id: UUID,
        holerite_id: UUID,
        funcionario_id: UUID,
        tipo: HoleriteItemTipo,
        origem: str,
        codigo: str,
        descricao: str,
        natureza: HoleriteItemNatureza,
        ordem: int,
        valor: Money,
        base: Money | None = None,
        regra_encargo_id: UUID | None = None,
        regra_grupo_id: UUID | None = None,
        snapshot_regra: dict | None = None,
        snapshot_calculo: dict | None = None,
        is_automatico: bool = True,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        if not origem.strip():
            raise DomainError("Origem do item do holerite e obrigatoria")
        if not codigo.strip():
            raise DomainError("Codigo do item do holerite e obrigatorio")
        if not descricao.strip():
            raise DomainError("Descricao do item do holerite e obrigatoria")
        if ordem < 0:
            raise DomainError("Ordem do item do holerite nao pode ser negativa")
        self.id = id or uuid4()
        self.team_id = team_id
        self.holerite_id = holerite_id
        self.funcionario_id = funcionario_id
        self.tipo = tipo
        self.origem = origem
        self.codigo = codigo
        self.descricao = descricao
        self.natureza = natureza
        self.ordem = ordem
        self.base = base or Money(Decimal("0.00"))
        self.valor = valor
        self.regra_encargo_id = regra_encargo_id
        self.regra_grupo_id = regra_grupo_id
        self.snapshot_regra = deepcopy(snapshot_regra) if snapshot_regra is not None else None
        self.snapshot_calculo = deepcopy(snapshot_calculo) if snapshot_calculo is not None else None
        self.is_automatico = is_automatico
        self.created_at = created_at or datetime.now(timezone.utc)

    @property
    def afeta_liquido(self) -> bool:
        return self.natureza in {HoleriteItemNatureza.PROVENTO, HoleriteItemNatureza.DESCONTO}


@dataclass
class FolhaCalculationContext:
    team_id: UUID
    holerite_id: UUID
    funcionario_id: UUID
    competencia_mes: int
    competencia_ano: int
    salario_base: Money
    horas_extras: Money
    descontos_falta: Money
    acrescimos_manuais: Money
    descontos_manuais: Money
    bruto_antes_encargos: Money
    bruto_antes_irrf: Money
    liquido_parcial: Money
    itens: list[HoleriteItem] = field(default_factory=list)


@dataclass
class FolhaCalculationResult:
    itens: list[HoleriteItem]
    total_proventos: Money
    total_descontos: Money
    total_informativos: Money
    valor_bruto: Money
    valor_liquido: Money


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
        valor_bruto: Money | None = None,
        total_proventos: Money | None = None,
        total_descontos: Money | None = None,
        total_informativos: Money | None = None,
        calculation_version: str | None = None,
        calculation_hash: str | None = None,
        calculated_at: datetime | None = None,
        calculated_by_user_id: UUID | None = None,
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
        self.valor_bruto = valor_bruto or Money(Decimal("0.00"))
        self.total_proventos = total_proventos or Money(Decimal("0.00"))
        self.total_descontos = total_descontos or Money(Decimal("0.00"))
        self.total_informativos = total_informativos or Money(Decimal("0.00"))
        self.calculation_version = calculation_version
        self.calculation_hash = calculation_hash
        self.calculated_at = calculated_at
        self.calculated_by_user_id = calculated_by_user_id
        self.is_deleted = False
        self.recalcular_valor_liquido()

    def recalcular_valor_liquido(self) -> None:
        self.valor_bruto = (
            self.salario_base
            + self.horas_extras
            + self.acrescimos_manuais
            - self.descontos_falta
        )
        self.total_proventos = self.salario_base + self.horas_extras + self.acrescimos_manuais
        self.total_descontos = self.descontos_falta + self.descontos_manuais
        self.total_informativos = Money(Decimal("0.00"))
        self.valor_liquido = self.valor_bruto - self.descontos_manuais

    def atualizar_totais_por_itens(self, itens: list[HoleriteItem]) -> None:
        proventos = Money(Decimal("0.00"))
        descontos = Money(Decimal("0.00"))
        informativos = Money(Decimal("0.00"))
        bruto = Money(Decimal("0.00"))

        for item in itens:
            if item.natureza == HoleriteItemNatureza.PROVENTO:
                proventos = proventos + item.valor
                bruto = bruto + item.valor
            elif item.natureza == HoleriteItemNatureza.DESCONTO:
                descontos = descontos + item.valor
                if item.tipo != HoleriteItemTipo.AJUSTE_MANUAL or item.codigo != "DESCONTO_MANUAL":
                    bruto = bruto - item.valor
            else:
                informativos = informativos + item.valor

        self.total_proventos = proventos
        self.total_descontos = descontos
        self.total_informativos = informativos
        self.valor_bruto = bruto
        self.valor_liquido = proventos - descontos

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


class RhFolhaJobStatus(Enum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    CONCLUIDO_COM_FALHAS = "concluido_com_falhas"
    FALHOU = "falhou"


class RhFolhaJob:
    def __init__(
        self,
        team_id: UUID,
        mes: int,
        ano: int,
        requested_by_user_id: UUID | None = None,
        funcionario_ids: list[UUID] | None = None,
        total_funcionarios: int = 0,
        processados: int = 0,
        falhas: int = 0,
        status: RhFolhaJobStatus = RhFolhaJobStatus.PENDENTE,
        error_summary: list[dict] | None = None,
        id: UUID | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> None:
        if mes < 1 or mes > 12:
            raise DomainError("Mes do job da folha invalido")
        if ano <= 0:
            raise DomainError("Ano do job da folha invalido")
        self.id = id or uuid4()
        self.team_id = team_id
        self.mes = mes
        self.ano = ano
        self.requested_by_user_id = requested_by_user_id
        self.funcionario_ids = list(funcionario_ids) if funcionario_ids else None
        self.total_funcionarios = total_funcionarios
        self.processados = processados
        self.falhas = falhas
        self.status = status
        self.error_summary = list(error_summary or [])
        self.started_at = started_at
        self.finished_at = finished_at
        self.created_at = created_at or datetime.now(timezone.utc)

    def mark_processing(self, total_funcionarios: int) -> None:
        self.status = RhFolhaJobStatus.PROCESSANDO
        self.total_funcionarios = total_funcionarios
        self.processados = 0
        self.falhas = 0
        self.error_summary = []
        self.started_at = datetime.now(timezone.utc)
        self.finished_at = None

    def register_success(self) -> None:
        self.processados += 1

    def register_failure(self, funcionario_id: UUID, error: str) -> None:
        self.processados += 1
        self.falhas += 1
        self.error_summary.append(
            {
                "funcionario_id": str(funcionario_id),
                "erro": error,
            }
        )

    def mark_completed(self) -> None:
        self.status = (
            RhFolhaJobStatus.CONCLUIDO_COM_FALHAS
            if self.falhas > 0
            else RhFolhaJobStatus.CONCLUIDO
        )
        self.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = RhFolhaJobStatus.FALHOU
        self.finished_at = datetime.now(timezone.utc)
        self.error_summary.append({"erro": error})


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
