"""Testes de pagamentos parcelados: criacao, edicao com propagacao e exclusao em grupo."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.entities.financeiro import MovClass, PagamentoAgendado, PaymentStatus
from app.domain.entities.money import Money
from app.domain.entities.user import Roles


def _make_user(team_id, role=Roles.ADMIN, user_id=None):
    return SimpleNamespace(
        id=user_id or uuid4(), nome="Ana", role=role,
        team=SimpleNamespace(id=team_id),
    )


def test_pagamento_agendado_aceita_campos_de_parcelamento(team_id):
    parcelamento_id = uuid4()
    p = PagamentoAgendado(
        team_id=team_id, title="Boleto", details="", valor=Money(Decimal("100.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
        parcelamento_id=parcelamento_id, parcela_numero=2, parcela_total=12,
    )
    assert p.parcelamento_id == parcelamento_id
    assert p.parcela_numero == 2
    assert p.parcela_total == 12


def test_pagamento_agendado_sem_parcelamento_tem_campos_nulos(team_id):
    p = PagamentoAgendado(
        team_id=team_id, title="Avulso", details="", valor=Money(Decimal("100.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
    )
    assert p.parcelamento_id is None
    assert p.parcela_numero is None
    assert p.parcela_total is None
