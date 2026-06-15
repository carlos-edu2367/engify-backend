from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.money import Money
from app.domain.entities.rh import Beneficio
from app.domain.errors import DomainError


def test_beneficio_default_valor_dia_zero():
    b = Beneficio(team_id=uuid4(), nome="Vale Refeicao")
    assert b.valor_dia == Money(Decimal("0.00"))


def test_beneficio_aceita_valor_dia():
    b = Beneficio(team_id=uuid4(), nome="VR", valor_dia=Money(Decimal("25.50")))
    assert b.valor_dia == Money(Decimal("25.50"))


def test_beneficio_valor_dia_negativo_invalido():
    with pytest.raises(DomainError):
        Beneficio(team_id=uuid4(), nome="VR", valor_dia=Money(Decimal("-1.00")))


def test_beneficio_atualizar_valor_dia():
    b = Beneficio(team_id=uuid4(), nome="VR")
    b.atualizar(valor_dia=Money(Decimal("30.00")))
    assert b.valor_dia == Money(Decimal("30.00"))
