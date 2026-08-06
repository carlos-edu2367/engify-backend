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


from app.application.dtos.financeiro import CreatePagamentoParceladoDTO
from app.application.services.financeiro_service import FinanceiroService
from app.domain.errors import DomainError


def _make_service(pagamentos=None):
    """Servico com repositorios mockados; `pagamentos` recebe tudo que for salvo."""
    pagamentos = pagamentos if pagamentos is not None else []

    pag_repo = AsyncMock()

    async def save_pagamento(p):
        if p.id is None:
            p.id = uuid4()
            pagamentos.append(p)
        return p

    async def get_by_id(pag_id, team_id=None):
        for p in pagamentos:
            if p.id == pag_id and (team_id is None or p.team_id == team_id):
                return p
        raise DomainError("Pagamento nao encontrado")

    pag_repo.save = AsyncMock(side_effect=save_pagamento)
    pag_repo.get_by_id = AsyncMock(side_effect=get_by_id)
    pag_repo.list_by_parcelamento = AsyncMock(
        side_effect=lambda pid, team_id: sorted(
            [p for p in pagamentos if p.parcelamento_id == pid and p.team_id == team_id],
            key=lambda p: p.parcela_numero,
        )
    )
    pag_repo.delete_unpaid = AsyncMock(return_value=True)

    diarist_repo = AsyncMock()
    diarist_repo.get_by_id = AsyncMock(side_effect=DomainError("nao encontrado"))

    svc = FinanceiroService(
        mov_repo=AsyncMock(),
        pagamento_repo=pag_repo,
        mov_attachment_repo=AsyncMock(),
        pagamento_attachment_repo=AsyncMock(),
        diarist_repo=diarist_repo,
        uow=AsyncMock(),
    )
    return svc, pag_repo, pagamentos


def _dto(parcelas=3, valor="1000.00", payment_cods=None):
    return CreatePagamentoParceladoDTO(
        title="Boleto obra", details="Material", valor=Decimal(valor),
        classe=MovClass.MATERIAL,
        data_agendada=datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc),
        parcelas=parcelas, payment_cods=payment_cods,
    )


@pytest.mark.asyncio
async def test_cria_n_parcelas_com_rateio_e_datas(team_id):
    svc, _, salvos = _make_service()
    actor = _make_user(team_id)

    parcelas = await svc.create_pagamento_parcelado(_dto(), team_id, actor_user=actor)

    assert len(parcelas) == 3
    assert [p.valor.amount for p in parcelas] == [
        Decimal("333.33"), Decimal("333.33"), Decimal("333.34"),
    ]
    assert [p.data_agendada.date().isoformat() for p in parcelas] == [
        "2026-01-31", "2026-02-28", "2026-03-31",
    ]
    assert [p.parcela_numero for p in parcelas] == [1, 2, 3]
    assert all(p.parcela_total == 3 for p in parcelas)
    assert len({p.parcelamento_id for p in parcelas}) == 1
    assert len(salvos) == 3


@pytest.mark.asyncio
async def test_titulo_recebe_sufixo_de_parcela(team_id):
    svc, _, _ = _make_service()
    parcelas = await svc.create_pagamento_parcelado(
        _dto(), team_id, actor_user=_make_user(team_id)
    )
    assert parcelas[0].title == "Boleto obra (1/3)"
    assert parcelas[2].title == "Boleto obra (3/3)"


@pytest.mark.asyncio
async def test_codigo_por_parcela_e_pix_individual(team_id):
    svc, _, _ = _make_service()
    parcelas = await svc.create_pagamento_parcelado(
        _dto(payment_cods=["11144477735", None, "11144477735"]),
        team_id, actor_user=_make_user(team_id),
    )
    assert parcelas[0].payment_cod == "11144477735"
    assert parcelas[1].payment_cod is None
    assert parcelas[1].pix_copy_and_past is None
    assert parcelas[0].pix_copy_and_past is not None
    # cada parcela gera um payload proprio, com o seu valor
    assert parcelas[0].pix_copy_and_past != parcelas[2].pix_copy_and_past


@pytest.mark.asyncio
async def test_engenheiro_precisa_de_codigo_apenas_na_primeira(team_id):
    svc, _, _ = _make_service()
    eng = _make_user(team_id, role=Roles.ENGENHEIRO)

    parcelas = await svc.create_pagamento_parcelado(
        _dto(payment_cods=["11144477735", None, None]), team_id, actor_user=eng,
    )
    assert len(parcelas) == 3

    with pytest.raises(DomainError, match="codigo de pagamento"):
        await svc.create_pagamento_parcelado(
            _dto(payment_cods=[None, "11144477735", None]), team_id, actor_user=eng,
        )


@pytest.mark.asyncio
async def test_rejeita_parcelas_fora_do_limite(team_id):
    svc, _, salvos = _make_service()
    actor = _make_user(team_id)

    for n in (1, 37):
        with pytest.raises(DomainError, match="parcelas"):
            await svc.create_pagamento_parcelado(_dto(parcelas=n), team_id, actor_user=actor)
    assert salvos == []


@pytest.mark.asyncio
async def test_rejeita_payment_cods_com_tamanho_errado(team_id):
    svc, _, salvos = _make_service()
    with pytest.raises(DomainError, match="codigos"):
        await svc.create_pagamento_parcelado(
            _dto(payment_cods=["a", "b"]), team_id, actor_user=_make_user(team_id),
        )
    assert salvos == []
