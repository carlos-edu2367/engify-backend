from decimal import Decimal

from app.domain.entities.money import Money
from app.domain.services.rh_ponto_calculo import (
    JornadaConfig,
    valor_minuto,
    valor_hora_extra,
)


def test_jornada_config_defaults():
    config = JornadaConfig()
    assert config.divisor_mensal_horas == Decimal("220")
    assert config.adicional_extra_percentual == Decimal("50")


def test_valor_minuto_usa_divisor_fixo():
    # 220h * 60 = 13.200 minutos; 2200 / 13200 = 0.1666... (Decimal cru, sem quantizar)
    salario = Money(Decimal("2200.00"))
    minuto = valor_minuto(salario, JornadaConfig())
    assert minuto.quantize(Decimal("0.0001")) == Decimal("0.1667")


def test_valor_hora_extra_aplica_adicional():
    salario = Money(Decimal("2200.00"))
    config = JornadaConfig(adicional_extra_percentual=Decimal("50"))
    # valor do minuto normal * 1.5, por 60 minutos
    extra_hora = valor_hora_extra(salario, Decimal("60"), config)
    esperado = (Decimal("2200.00") / Decimal("13200")) * Decimal("1.5") * Decimal("60")
    assert extra_hora.amount == esperado.quantize(Decimal("0.01"))
