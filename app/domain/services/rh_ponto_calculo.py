from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time as Time, timedelta, timezone, tzinfo
from enum import Enum
from decimal import Decimal
from typing import Callable

from app.domain.entities.money import Money
from app.domain.entities.rh import RegistroPonto, StatusPonto, TurnoHorario

_STATUS_VALIDOS = {StatusPonto.VALIDADO, StatusPonto.AJUSTADO}


@dataclass(frozen=True)
class JornadaConfig:
    """Parametros de calculo de ponto. Defaults intermediarios (divisor 220h, adicional 50%).

    Persistencia por team/funcionario fica para uma fase futura; hoje usa defaults.
    """

    divisor_mensal_horas: Decimal = Decimal("220")
    adicional_extra_percentual: Decimal = Decimal("50")


def valor_minuto(salario_base: Money, config: JornadaConfig) -> Decimal:
    """Valor de um minuto normal de trabalho, em Decimal cru (sem quantizar).

    Money quantiza para 2 casas, o que zeraria a precisao de um minuto; por isso
    retornamos Decimal e so convertemos para Money no valor monetario final.
    """
    return salario_base.amount / (config.divisor_mensal_horas * Decimal("60"))


def valor_falta(salario_base: Money, minutos_falta: Decimal, config: JornadaConfig) -> Money:
    bruto = valor_minuto(salario_base, config) * minutos_falta
    return Money(bruto.quantize(Decimal("0.01")))


def valor_hora_extra(salario_base: Money, minutos_extras: Decimal, config: JornadaConfig) -> Money:
    fator = Decimal("1") + (config.adicional_extra_percentual / Decimal("100"))
    bruto = valor_minuto(salario_base, config) * fator * minutos_extras
    return Money(bruto.quantize(Decimal("0.01")))


@dataclass(frozen=True)
class ResultadoDia:
    esperado_min: Decimal
    trabalhado_min: Decimal
    extra_min: Decimal
    falta_min: Decimal
    incompleto: bool


class SituacaoDia(str, Enum):
    SEM_EXPEDIENTE = "sem_expediente"
    ABONADO = "abonado"
    FALTA = "falta"
    INCOMPLETO = "incompleto"
    PARCIAL = "parcial"
    COMPLETO = "completo"
    EXTRA = "extra"


@dataclass(frozen=True)
class ResumoDia:
    data: date
    situacao: SituacaoDia
    esperado_min: Decimal
    trabalhado_min: Decimal
    extra_min: Decimal
    falta_min: Decimal


def _classificar_dia(resultado: ResultadoDia) -> SituacaoDia:
    """Traduz um ResultadoDia para a situacao exibida ao funcionario.

    A ordem importa: dia incompleto (batidas impares) nao e falta, e um dia
    com falta parcial nunca vira extra.
    """
    if resultado.incompleto:
        return SituacaoDia.INCOMPLETO
    if resultado.trabalhado_min == Decimal("0"):
        return SituacaoDia.FALTA
    if resultado.falta_min > Decimal("0"):
        return SituacaoDia.PARCIAL
    if resultado.extra_min > Decimal("0"):
        return SituacaoDia.EXTRA
    return SituacaoDia.COMPLETO


def _esperado_min(turno: TurnoHorario | None) -> Decimal:
    if turno is None:
        return Decimal("0")
    return Decimal(str(turno.horas_esperadas)) * Decimal("60")


def _hhmm_to_minutes(value: Time) -> Decimal:
    return Decimal(value.hour * 60 + value.minute)


def minutos_liberacao(turno: TurnoHorario, hora_corte: Time) -> Decimal:
    """Minutos esperados de trabalho entre a entrada do turno e a hora de corte.

    Usado para liberacao antecipada: a jornada esperada do dia passa a
    terminar em hora_corte em vez de hora_saida. Desconta os intervalos do
    turno que caem dentro dessa janela, do mesmo jeito que resultado_dia
    desconta o intervalo do span trabalhado.
    """
    entrada = _hhmm_to_minutes(turno.hora_entrada)
    corte = _hhmm_to_minutes(hora_corte)
    if corte <= entrada:
        return Decimal("0")
    bruto = corte - entrada
    intervalo_min = Decimal("0")
    for intervalo in turno.intervalos:
        inicio = max(entrada, _hhmm_to_minutes(intervalo.hora_inicio))
        fim = min(corte, _hhmm_to_minutes(intervalo.hora_fim))
        if fim > inicio:
            intervalo_min += fim - inicio
    return max(Decimal("0"), bruto - intervalo_min)


def resultado_dia(registros: list[RegistroPonto], turno: TurnoHorario | None, esperado_min_override: Decimal | None = None) -> ResultadoDia:
    """turno pode ser None: dia sem turno cadastrado (ex.: domingo fora de escala) em que o
    colaborador bateu ponto mesmo assim. Sem turno nao ha esperado nem intervalo conhecido, entao
    o span inteiro trabalhado vira hora extra (esperado=0, intervalo=0)."""
    esperado = esperado_min_override if esperado_min_override is not None else _esperado_min(turno)
    validos = sorted(
        [r for r in registros if r.status in _STATUS_VALIDOS],
        key=lambda r: r.timestamp,
    )
    if not validos:
        return ResultadoDia(esperado, Decimal("0"), Decimal("0"), esperado, incompleto=False)
    if len(validos) % 2 != 0:
        return ResultadoDia(esperado, Decimal("0"), Decimal("0"), Decimal("0"), incompleto=True)

    span_min = Decimal(str((validos[-1].timestamp - validos[0].timestamp).total_seconds() / 60))
    intervalo_min = Decimal(str(sum(i.minutos for i in turno.intervalos))) if turno is not None else Decimal("0")
    trabalhado = max(Decimal("0"), span_min - intervalo_min)
    extra = max(Decimal("0"), trabalhado - esperado)
    falta = max(Decimal("0"), esperado - trabalhado)
    return ResultadoDia(esperado, trabalhado, extra, falta, incompleto=False)


def _abater_minutos_abonados(resultado: ResultadoDia, minutos: Decimal) -> ResultadoDia:
    """Abate as horas devidas que o RH perdoou, sem nunca passar da divida do dia.

    Dia incompleto (batidas impares) nao tem divida calculavel e fica como
    esta ate o ponto ser corrigido.
    """
    if minutos <= Decimal("0") or resultado.incompleto:
        return resultado
    return ResultadoDia(
        esperado_min=resultado.esperado_min,
        trabalhado_min=resultado.trabalhado_min,
        extra_min=resultado.extra_min,
        falta_min=max(Decimal("0"), resultado.falta_min - minutos),
        incompleto=False,
    )


@dataclass(frozen=True)
class ResumoPeriodo:
    esperado_min: Decimal
    extra_min: Decimal
    falta_min: Decimal
    faltas: int
    dias_incompletos: int
    pontos_inconsistentes: int
    dias: tuple[ResumoDia, ...] = ()


def resumir_periodo(
    registros: list[RegistroPonto],
    turno_para_dia: Callable[[int], TurnoHorario | None],
    inicio: date,
    fim: date,
    datas_abonadas: set[date],
    liberacoes: dict[date, Decimal] | None = None,
    minutos_abonados: dict[date, Decimal] | None = None,
    *,
    tz: tzinfo = timezone.utc,
) -> ResumoPeriodo:
    """Agrega resultado_dia() para cada dia com turno no periodo.

    liberacoes mapeia data -> minutos esperados reduzidos (ex.: liberacao
    antecipada). Quando presente para uma data, substitui o esperado do turno
    para aquele dia, evitando que a saida antecipada autorizada vire falta.

    minutos_abonados mapeia data -> minutos perdoados pelo RH naquele dia.
    Diferente da liberacao, nao mexe no esperado: so abate as horas devidas,
    e nunca passa delas, entao nao cria hora extra nem credito.

    tz define o fuso usado para decidir a que dia cada batida pertence. Em
    UTC-3, uma batida as 23h locais chega como o dia seguinte em UTC; agrupar
    por UTC jogaria essa batida para o dia errado.
    """
    liberacoes = liberacoes or {}
    minutos_abonados = minutos_abonados or {}
    por_dia: dict[date, list[RegistroPonto]] = defaultdict(list)
    pontos_inconsistentes = 0
    for r in registros:
        dia = r.timestamp.astimezone(tz).date()
        por_dia[dia].append(r)
        if r.status == StatusPonto.INCONSISTENTE:
            pontos_inconsistentes += 1

    esperado_total = Decimal("0")
    extra_total = Decimal("0")
    falta_total = Decimal("0")
    faltas = 0
    dias_incompletos = 0

    atual = inicio
    dias: list[ResumoDia] = []
    while atual <= fim:
        turno = turno_para_dia(atual.weekday())
        registros_dia = por_dia.get(atual, [])
        tem_batida_valida = any(r.status in _STATUS_VALIDOS for r in registros_dia)
        if turno is None and not tem_batida_valida:
            # Sem turno cadastrado e sem nenhuma batida valida: dia realmente
            # sem expediente (ex.: domingo comum). Se houver batida valida
            # mesmo sem turno, cai no ramo abaixo e conta como hora extra em
            # vez de sumir do resumo.
            dias.append(
                ResumoDia(
                    data=atual,
                    situacao=SituacaoDia.SEM_EXPEDIENTE,
                    esperado_min=Decimal("0"),
                    trabalhado_min=Decimal("0"),
                    extra_min=Decimal("0"),
                    falta_min=Decimal("0"),
                )
            )
            atual += timedelta(days=1)
            continue

        esperado_dia = liberacoes.get(atual, _esperado_min(turno))
        esperado_total += esperado_dia
        r = None
        if atual not in datas_abonadas:
            r = _abater_minutos_abonados(
                resultado_dia(registros_dia, turno, esperado_min_override=esperado_dia),
                minutos_abonados.get(atual, Decimal("0")),
            )
        # Dia sem trabalho cuja divida inteira foi perdoada em minutos e, na
        # pratica, um dia abonado: nao pode contar como falta.
        dia_todo_perdoado = (
            r is not None
            and not r.incompleto
            and r.trabalhado_min == Decimal("0")
            and r.falta_min == Decimal("0")
            and esperado_dia > Decimal("0")
        )
        if r is None or dia_todo_perdoado:
            dias.append(
                ResumoDia(
                    data=atual,
                    situacao=SituacaoDia.ABONADO,
                    esperado_min=esperado_dia,
                    trabalhado_min=Decimal("0"),
                    extra_min=Decimal("0"),
                    falta_min=Decimal("0"),
                )
            )
        else:
            extra_total += r.extra_min
            falta_total += r.falta_min
            if r.incompleto:
                dias_incompletos += 1
            elif r.trabalhado_min == Decimal("0"):
                faltas += 1
            dias.append(
                ResumoDia(
                    data=atual,
                    situacao=_classificar_dia(r),
                    esperado_min=esperado_dia,
                    trabalhado_min=r.trabalhado_min,
                    extra_min=r.extra_min,
                    falta_min=r.falta_min,
                )
            )
        atual += timedelta(days=1)

    return ResumoPeriodo(
        esperado_min=esperado_total,
        extra_min=extra_total,
        falta_min=falta_total,
        faltas=faltas,
        dias_incompletos=dias_incompletos,
        pontos_inconsistentes=pontos_inconsistentes,
        dias=tuple(dias),
    )
