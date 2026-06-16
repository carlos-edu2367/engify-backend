from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.services.rh_folha_service import RhFolhaService
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Beneficio, BeneficioFuncionario, HoleriteItemTipo, RegistroPonto, StatusPonto, TipoPonto,
)


def _service():
    return RhFolhaService.__new__(RhFolhaService)


def test_build_beneficio_items_usa_dias_presenca():
    svc = _service()
    team_id, func_id = uuid4(), uuid4()
    holerite = type("H", (), {
        "team_id": team_id, "id": uuid4(), "funcionario_id": func_id,
        "mes_referencia": 6, "ano_referencia": 2026,
    })()
    beneficio = Beneficio(team_id=team_id, nome="VR", valor_dia=Money(Decimal("25.00")))
    vinculos = [BeneficioFuncionario(team_id=team_id, beneficio_id=beneficio.id, funcionario_id=func_id)]
    beneficios_por_id = {beneficio.id: beneficio}
    registros = [
        RegistroPonto(team_id=team_id, funcionario_id=func_id, tipo=TipoPonto.ENTRADA,
                      timestamp=datetime(2026, 6, 1, 8, tzinfo=timezone.utc),
                      latitude=0.0, longitude=0.0, status=StatusPonto.VALIDADO),
        RegistroPonto(team_id=team_id, funcionario_id=func_id, tipo=TipoPonto.ENTRADA,
                      timestamp=datetime(2026, 6, 2, 8, tzinfo=timezone.utc),
                      latitude=0.0, longitude=0.0, status=StatusPonto.VALIDADO),
    ]
    items = svc._build_beneficio_items(holerite, vinculos, beneficios_por_id, registros)
    assert len(items) == 1
    item = items[0]
    assert item.tipo == HoleriteItemTipo.BENEFICIO_AUTOMATICO
    # 22 working days in Jun/2026, 2 present => 20 faltas => 2 paid days => 50.00
    assert item.valor == Money(Decimal("50.00"))
