"""Testes do ObraFinanceiroResumoService (unitarios puros, sem DB e sem HTTP)."""
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.entities.money import Money
from app.domain.entities.obra import Obra
from app.application.services.obra_financeiro_resumo_service import (
    ObraFinanceiroResumoService,
)


def _make_obra(team_id, obra_id, valor=None, total_recebido="0"):
    return Obra(
        title="Obra Teste",
        team_id=team_id,
        responsavel_id=uuid4(),
        description="",
        id=obra_id,
        valor=Money(Decimal(valor)) if valor is not None else None,
        total_recebido=Decimal(total_recebido),
    )


def _make_service(obra, resumo_rows, comprometido_rows):
    obra_repo = AsyncMock()
    obra_repo.get_by_id = AsyncMock(return_value=obra)

    mov_repo = AsyncMock()
    mov_repo.get_resumo_obra = AsyncMock(return_value=resumo_rows)

    pagamento_repo = AsyncMock()
    pagamento_repo.get_comprometido_obra = AsyncMock(return_value=comprometido_rows)

    service = ObraFinanceiroResumoService(
        obra_repo=obra_repo, mov_repo=mov_repo, pagamento_repo=pagamento_repo,
    )
    return service, obra_repo, mov_repo, pagamento_repo


@pytest.mark.asyncio
async def test_caminho_feliz_com_contrato(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="150000.00", total_recebido="50000.00")
    resumo_rows = [
        {"type": "entrada", "classe": "contrato", "total": Decimal("50000.00"), "qtd": 1},
        {"type": "saida", "classe": "material", "total": Decimal("20000.00"), "qtd": 1},
        {"type": "saida", "classe": "servico", "total": Decimal("12000.00"), "qtd": 1},
    ]
    comprometido_rows = [
        {"classe": "diarista", "total": Decimal("18000.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, comprometido_rows)

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.contrato == Decimal("150000.00")
    assert dto.entradas == Decimal("50000.00")
    assert dto.saidas == Decimal("32000.00")
    assert dto.comprometido == Decimal("18000.00")
    assert dto.resultado_realizado == Decimal("18000.00")
    assert dto.custo_previsto == Decimal("50000.00")
    assert dto.margem_projetada == Decimal("100000.00")
    assert dto.margem_projetada_pct == Decimal("66.67")
    assert dto.a_receber == Decimal("100000.00")
    assert dto.qtd_movimentacoes == 3
    assert dto.qtd_pagamentos_aguardando == 1


@pytest.mark.asyncio
async def test_contrato_null_zera_campos_derivados(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor=None, total_recebido="0")
    resumo_rows = [
        {"type": "saida", "classe": "material", "total": Decimal("1000.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, [])

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.contrato is None
    assert dto.margem_projetada is None
    assert dto.margem_projetada_pct is None
    assert dto.a_receber is None
    assert dto.resultado_realizado == Decimal("-1000.00")
    assert dto.custo_previsto == Decimal("1000.00")


@pytest.mark.asyncio
async def test_contrato_zero_nao_divide_por_zero(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="0", total_recebido="0")
    resumo_rows = [
        {"type": "saida", "classe": "material", "total": Decimal("500.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, [])

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.contrato == Decimal("0.00")
    assert dto.margem_projetada == Decimal("-500.00")
    assert dto.margem_projetada_pct is None


@pytest.mark.asyncio
async def test_obra_sem_lancamentos_zera_tudo(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="10000.00", total_recebido="0")
    service, *_ = _make_service(obra, [], [])

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.entradas == Decimal("0")
    assert dto.saidas == Decimal("0")
    assert dto.comprometido == Decimal("0")
    assert dto.resultado_realizado == Decimal("0")
    assert dto.custo_previsto == Decimal("0")
    assert dto.custos_por_classe == []
    assert dto.qtd_movimentacoes == 0
    assert dto.qtd_pagamentos_aguardando == 0


@pytest.mark.asyncio
async def test_margem_negativa_sem_clamp(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="1000.00", total_recebido="0")
    resumo_rows = [
        {"type": "saida", "classe": "material", "total": Decimal("1500.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, [])

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.margem_projetada == Decimal("-500.00")
    assert dto.margem_projetada_pct == Decimal("-50.00")


@pytest.mark.asyncio
async def test_custos_por_classe_mescla_realizado_e_comprometido(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="10000.00")
    resumo_rows = [
        # so realizado
        {"type": "saida", "classe": "material", "total": Decimal("300.00"), "qtd": 1},
        # presente nos dois
        {"type": "saida", "classe": "servico", "total": Decimal("100.00"), "qtd": 1},
    ]
    comprometido_rows = [
        # so comprometido
        {"classe": "diarista", "total": Decimal("400.00"), "qtd": 1},
        # presente nos dois
        {"classe": "servico", "total": Decimal("50.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, comprometido_rows)

    dto = await service.get_resumo(obra_id, team_id)

    by_classe = {c.classe.value: c for c in dto.custos_por_classe}
    assert set(by_classe.keys()) == {"material", "servico", "diarista"}
    assert by_classe["servico"].realizado == Decimal("100.00")
    assert by_classe["servico"].comprometido == Decimal("50.00")
    assert by_classe["material"].realizado == Decimal("300.00")
    assert by_classe["material"].comprometido == Decimal("0")
    assert by_classe["diarista"].realizado == Decimal("0")
    assert by_classe["diarista"].comprometido == Decimal("400.00")
    # ordenado desc por realizado + comprometido: diarista(400) > material(300) > servico(150)
    assert [c.classe.value for c in dto.custos_por_classe] == ["diarista", "material", "servico"]


@pytest.mark.asyncio
async def test_entradas_nao_entram_em_custos_por_classe(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="10000.00")
    resumo_rows = [
        {"type": "entrada", "classe": "material", "total": Decimal("999.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, [])

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.custos_por_classe == []
    assert dto.entradas == Decimal("999.00")


@pytest.mark.asyncio
async def test_total_recebido_obra_independe_das_entradas(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="10000.00", total_recebido="40000.00")
    resumo_rows = [
        {"type": "entrada", "classe": "contrato", "total": Decimal("50000.00"), "qtd": 1},
    ]
    service, *_ = _make_service(obra, resumo_rows, [])

    dto = await service.get_resumo(obra_id, team_id)

    assert dto.entradas == Decimal("50000.00")
    assert dto.total_recebido_obra == Decimal("40000.00")


@pytest.mark.asyncio
async def test_isolamento_de_tenant_repassado_aos_repos(team_id):
    obra_id = uuid4()
    obra = _make_obra(team_id, obra_id, valor="1000.00")
    service, obra_repo, mov_repo, pagamento_repo = _make_service(obra, [], [])

    await service.get_resumo(obra_id, team_id)

    obra_repo.get_by_id.assert_awaited_once_with(obra_id, team_id)
    mov_repo.get_resumo_obra.assert_awaited_once_with(obra_id, team_id)
    pagamento_repo.get_comprometido_obra.assert_awaited_once_with(obra_id, team_id)
