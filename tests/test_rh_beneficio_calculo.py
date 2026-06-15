from datetime import date
from decimal import Decimal

from app.domain.entities.money import Money
from app.domain.services.rh_beneficio_calculo import (
    dias_uteis_competencia,
    contar_faltas,
    valor_beneficio,
)


def test_dias_uteis_junho_2026():
    assert dias_uteis_competencia(6, 2026) == 22


def test_contar_faltas_conta_dias_uteis_sem_presenca():
    dias_presenca = {date(2026, 6, 1), date(2026, 6, 2)}
    faltas = contar_faltas(6, 2026, dias_presenca)
    assert faltas == dias_uteis_competencia(6, 2026) - 2


def test_contar_faltas_ignora_presenca_em_fim_de_semana():
    dias_presenca = {date(2026, 6, 6)}  # Saturday
    faltas = contar_faltas(6, 2026, dias_presenca)
    assert faltas == dias_uteis_competencia(6, 2026)


def test_valor_beneficio():
    assert valor_beneficio(Money(Decimal("25.00")), dias_uteis=22, faltas=2) == Money(Decimal("500.00"))


def test_valor_beneficio_nunca_negativo():
    assert valor_beneficio(Money(Decimal("25.00")), dias_uteis=5, faltas=10) == Money(Decimal("0.00"))
