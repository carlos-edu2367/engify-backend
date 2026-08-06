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


from app.application.dtos.financeiro import CreatePagamentoDTO, EditPagamentoDTO


async def _criar_parcelamento(svc, team_id, actor, parcelas=4):
    return await svc.create_pagamento_parcelado(
        _dto(parcelas=parcelas, valor="400.00"), team_id, actor_user=actor,
    )


@pytest.mark.asyncio
async def test_edicao_self_nao_toca_nas_outras_parcelas(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)

    dto = EditPagamentoDTO(title="Novo titulo", apply_to="self")
    await svc.edit_pagamento(parcelas[1], dto, actor_user=actor)

    assert parcelas[1].title == "Novo titulo"
    assert parcelas[2].title != "Novo titulo"
    assert parcelas[0].title != "Novo titulo"


@pytest.mark.asyncio
async def test_edicao_future_propaga_campos_comuns(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)

    dto = EditPagamentoDTO(
        title="Reforma", details="Nova descricao", valor=Decimal("150.00"),
        classe=MovClass.SERVICO, apply_to="future",
    )
    await svc.edit_pagamento(parcelas[1], dto, actor_user=actor)

    for p in parcelas[1:]:
        assert p.title == "Reforma"
        assert p.details == "Nova descricao"
        assert p.valor.amount == Decimal("150.00")
        assert p.classe == MovClass.SERVICO
    # parcela anterior intocada
    assert parcelas[0].title != "Reforma"
    assert parcelas[0].valor.amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_edicao_future_nao_propaga_data_nem_codigo(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)
    data_original = parcelas[2].data_agendada
    cod_original = parcelas[2].payment_cod

    dto = EditPagamentoDTO(
        data_agendada=datetime(2027, 7, 7, tzinfo=timezone.utc),
        payment_cod="11144477735", apply_to="future",
    )
    await svc.edit_pagamento(parcelas[1], dto, actor_user=actor)

    assert parcelas[1].data_agendada.year == 2027
    assert parcelas[1].payment_cod == "11144477735"
    assert parcelas[2].data_agendada == data_original
    assert parcelas[2].payment_cod == cod_original


@pytest.mark.asyncio
async def test_edicao_future_ignora_parcelas_ja_pagas(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)
    parcelas[3].status = PaymentStatus.PAGO
    titulo_pago = parcelas[3].title

    dto = EditPagamentoDTO(title="Reforma", apply_to="future")
    await svc.edit_pagamento(parcelas[1], dto, actor_user=actor)

    assert parcelas[2].title == "Reforma"
    assert parcelas[3].title == titulo_pago


@pytest.mark.asyncio
async def test_edicao_future_em_pagamento_avulso_age_como_self(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    avulso = await svc.create_pagamento(
        CreatePagamentoDTO(
            title="Avulso", details="", valor=Decimal("50.00"), classe=MovClass.FIXO,
            data_agendada=datetime(2026, 3, 1, tzinfo=timezone.utc),
        ),
        team_id, actor_user=actor,
    )

    dto = EditPagamentoDTO(title="Editado", apply_to="future")
    editado = await svc.edit_pagamento(avulso, dto, actor_user=actor)

    assert editado.title == "Editado"


@pytest.mark.asyncio
async def test_delete_self_remove_apenas_a_parcela(team_id):
    svc, pag_repo, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)

    removidos = await svc.delete_pagamento(parcelas[1].id, team_id, actor_user=actor)

    assert removidos == 1
    assert pag_repo.delete_unpaid.await_count == 1


@pytest.mark.asyncio
async def test_delete_scope_parcelamento_remove_todas_aguardando(team_id):
    svc, pag_repo, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)
    parcelas[0].status = PaymentStatus.PAGO

    removidos = await svc.delete_pagamento(
        parcelas[1].id, team_id, actor_user=actor, scope="parcelamento",
    )

    # 4 parcelas, 1 ja paga -> 3 removidas
    assert removidos == 3
    ids_removidos = {c.args[0] for c in pag_repo.delete_unpaid.await_args_list}
    assert parcelas[0].id not in ids_removidos


@pytest.mark.asyncio
async def test_delete_scope_parcelamento_em_avulso_remove_um(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    avulso = await svc.create_pagamento(
        CreatePagamentoDTO(
            title="Avulso", details="", valor=Decimal("50.00"), classe=MovClass.FIXO,
            data_agendada=datetime(2026, 3, 1, tzinfo=timezone.utc),
        ),
        team_id, actor_user=actor,
    )

    removidos = await svc.delete_pagamento(
        avulso.id, team_id, actor_user=actor, scope="parcelamento",
    )
    assert removidos == 1


@pytest.mark.asyncio
async def test_delete_parcela_ja_paga_rejeitado(team_id):
    svc, _, _ = _make_service()
    actor = _make_user(team_id)
    parcelas = await _criar_parcelamento(svc, team_id, actor)
    parcelas[1].status = PaymentStatus.PAGO

    with pytest.raises(DomainError, match="ja foi efetuado"):
        await svc.delete_pagamento(parcelas[1].id, team_id, actor_user=actor)
