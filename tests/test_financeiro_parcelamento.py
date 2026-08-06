"""Testes das funcoes puras de calculo de parcelamento (sem I/O)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.application.services.financeiro_parcelamento import (
    build_datas_parcelas, split_valor_parcelas,
)


def test_split_distribui_residuo_na_ultima_parcela():
    assert split_valor_parcelas(Decimal("1000.00"), 3) == [
        Decimal("333.33"), Decimal("333.33"), Decimal("333.34"),
    ]


def test_split_soma_sempre_igual_ao_total():
    for total in ("1000.00", "0.03", "99.99", "1234.57"):
        for n in (2, 3, 7, 36):
            valores = split_valor_parcelas(Decimal(total), n)
            assert sum(valores) == Decimal(total)
            assert len(valores) == n


def test_split_valor_exato_nao_gera_residuo():
    assert split_valor_parcelas(Decimal("900.00"), 3) == [
        Decimal("300.00"), Decimal("300.00"), Decimal("300.00"),
    ]


def test_split_rejeita_parcelas_fora_do_limite():
    with pytest.raises(ValueError):
        split_valor_parcelas(Decimal("100.00"), 1)
    with pytest.raises(ValueError):
        split_valor_parcelas(Decimal("100.00"), 37)


def test_datas_avancam_um_mes():
    primeira = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    datas = build_datas_parcelas(primeira, 3)
    assert [d.date().isoformat() for d in datas] == [
        "2026-01-10", "2026-02-10", "2026-03-10",
    ]


def test_datas_fazem_clamp_no_fim_do_mes():
    primeira = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    datas = build_datas_parcelas(primeira, 4)
    assert [d.date().isoformat() for d in datas] == [
        "2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30",
    ]


def test_datas_clamp_em_ano_bissexto():
    primeira = datetime(2028, 1, 31, 12, 0, tzinfo=timezone.utc)
    datas = build_datas_parcelas(primeira, 2)
    assert datas[1].date().isoformat() == "2028-02-29"


def test_datas_preservam_hora_e_timezone():
    primeira = datetime(2026, 5, 15, 9, 30, tzinfo=timezone.utc)
    datas = build_datas_parcelas(primeira, 2)
    assert datas[1].hour == 9 and datas[1].minute == 30
    assert datas[1].tzinfo == timezone.utc
