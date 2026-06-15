from decimal import Decimal
from uuid import uuid4

from app.domain.entities.money import Money
from app.domain.entities.rh import Beneficio
from app.infra.db.models.rh_model import BeneficioModel


def test_from_domain_persiste_valor_dia():
    b = Beneficio(team_id=uuid4(), nome="VR", valor_dia=Money(Decimal("25.50")))
    model = BeneficioModel.from_domain(b)
    assert model.valor_dia == Decimal("25.50")


def test_to_domain_restaura_valor_dia():
    b = Beneficio(team_id=uuid4(), nome="VR", valor_dia=Money(Decimal("12.00")))
    model = BeneficioModel.from_domain(b)
    restored = model.to_domain()
    assert restored.valor_dia == Money(Decimal("12.00"))
