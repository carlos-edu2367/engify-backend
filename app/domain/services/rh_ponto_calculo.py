from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta, timezone
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


def _esperado_min(turno: TurnoHorario) -> Decimal:
    return Decimal(str(turno.horas_esperadas)) * Decimal("60")


def resultado_dia(registros: list[RegistroPonto], turno: TurnoHorario, esperado_min_override: Decimal | None = None) -> ResultadoDia:
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
    intervalo_min = Decimal(str(sum(i.minutos for i in turno.intervalos)))
    trabalhado = max(Decimal("0"), span_min - intervalo_min)
    extra = max(Decimal("0"), trabalhado - esperado)
    falta = max(Decimal("0"), esperado - trabalhado)
    return ResultadoDia(esperado, trabalhado, extra, falta, incompleto=False)


@dataclass(frozen=True)
class ResumoPeriodo:
    esperado_min: Decimal
    extra_min: Decimal
    falta_min: Decimal
    faltas: int
    dias_incompletos: int
    pontos_inconsistentes: int


def resumir_periodo(
    registros: list[RegistroPonto],
    turno_para_dia: Callable[[int], TurnoHorario | None],
    inicio: date,
    fim: date,
    datas_abonadas: set[date],
    liberacoes: dict[date, Decimal] | None = None,
) -> ResumoPeriodo:
    """Agrega resultado_dia() para cada dia com turno no periodo.

    liberacoes mapeia data -> minutos esperados reduzidos (ex.: liberacao
    antecipada). Quando presente para uma data, substitui o esperado do turno
    para aquele dia, evitando que a saida antecipada autorizada vire falta.
    """
    liberacoes = liberacoes or {}
    por_dia: dict[date, list[RegistroPonto]] = defaultdict(list)
    pontos_inconsistentes = 0
    for r in registros:
        dia = r.timestamp.astimezone(timezone.utc).date()
        por_dia[dia].append(r)
        if r.status == StatusPonto.INCONSISTENTE:
            pontos_inconsistentes += 1

    esperado_total = Decimal("0")
    extra_total = Decimal("0")
    falta_total = Decimal("0")
    faltas = 0
    dias_incompletos = 0

    atual = inicio
    while atual <= fim:
        turno = turno_para_dia(atual.weekday())
        if turno is not None:
            esperado_dia = liberacoes.get(atual, _esperado_min(turno))
            esperado_total += esperado_dia
            if atual not in datas_abonadas:
                r = resultado_dia(por_dia.get(atual, []), turno, esperado_min_override=esperado_dia)
                extra_total += r.extra_min
                falta_total += r.falta_min
                if r.incompleto:
                    dias_incompletos += 1
                elif r.trabalhado_min == Decimal("0"):
                    faltas += 1
        atual += timedelta(days=1)

    return ResumoPeriodo(
        esperado_min=esperado_total,
        extra_min=extra_total,
        falta_min=falta_total,
        faltas=faltas,
        dias_incompletos=dias_incompletos,
        pontos_inconsistentes=pontos_inconsistentes,
    )
