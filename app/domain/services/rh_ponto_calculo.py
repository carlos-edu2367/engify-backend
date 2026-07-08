from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal

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


def resultado_dia(registros: list[RegistroPonto], turno: TurnoHorario) -> ResultadoDia:
    esperado = _esperado_min(turno)
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
