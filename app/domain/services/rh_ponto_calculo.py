from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.money import Money


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
