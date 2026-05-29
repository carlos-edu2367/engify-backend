"""
Testes unitários para FinanceiroService.pay_lote.

Todos os testes são síncronos com mocks puros — sem banco de dados.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.application.dtos.financeiro import BaixaLoteDTO
from app.application.services.financeiro_service import FinanceiroService, _fmt_brl, _build_lote_descricao
from app.domain.entities.financeiro import (
    PagamentoAgendado, PaymentStatus, MovClass, Movimentacao, MovimentacaoTypes,
)
from app.domain.entities.money import Money
from app.domain.errors import DomainError


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pagamento(team_id, valor: str = "100.00",
                    status: PaymentStatus = PaymentStatus.AGUARDANDO,
                    pag_id=None) -> PagamentoAgendado:
    p = object.__new__(PagamentoAgendado)
    p.id = pag_id or uuid4()
    p.team_id = team_id
    p.title = "Serviço de pintura"
    p.details = "Detalhe"
    p.valor = Money(Decimal(valor))
    p.classe = MovClass.SERVICO
    p.data_agendada = datetime.now(timezone.utc)
    p.payment_cod = None
    p.pix_copy_and_past = None
    p.status = status
    p.payment_date = None
    p.obra_id = None
    p.diarist_id = None
    return p


def _make_service(pagamentos_retornados, movimentacao_salva=None):
    """Monta um FinanceiroService com repos totalmente mockados."""
    mov_repo = AsyncMock()
    pag_repo = AsyncMock()
    uow = AsyncMock()

    def _get_pagamento_by_id(pag_id, team_id=None):
        for pagamento in pagamentos_retornados:
            if pagamento.id == pag_id and (team_id is None or pagamento.team_id == team_id):
                return pagamento
        raise DomainError("Pagamento nao encontrado")

    pag_repo.list_by_ids.return_value = pagamentos_retornados
    pag_repo.get_by_id = AsyncMock(side_effect=_get_pagamento_by_id)
    pag_repo.save = AsyncMock(side_effect=lambda p: p)
    pag_repo.delete_unpaid = AsyncMock(return_value=True)

    if movimentacao_salva is None:
        mov_salvo = object.__new__(Movimentacao)
        mov_salvo.id = uuid4()
        mov_salvo.title = "mock"
        mov_salvo.type = MovimentacaoTypes.SAIDA
        mov_salvo.valor = Money(Decimal("100"))
        mov_salvo.lote_info = None
        movimentacao_salva = mov_salvo

    mov_repo.save = AsyncMock(return_value=movimentacao_salva)

    svc = FinanceiroService(
        mov_repo=mov_repo,
        pagamento_repo=pag_repo,
        mov_attachment_repo=AsyncMock(),
        diarist_repo=AsyncMock(),
        uow=uow,
    )
    return svc, pag_repo, mov_repo, uow


# ── testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lote_valido_completo(team_id):
    """Lote com pagamentos válidos: status corretos, total e commit chamados."""
    p1 = _make_pagamento(team_id, "200.00")
    p2 = _make_pagamento(team_id, "350.50")
    svc, pag_repo, mov_repo, uow = _make_service([p1, p2])

    dto = BaixaLoteDTO(pagamento_ids=[p1.id, p2.id], team_id=team_id)
    resultado = await svc.pay_lote(dto)

    assert resultado.quantidade == 2
    assert resultado.valor_total == Decimal("550.50")
    assert p1.status == PaymentStatus.PAGO
    assert p2.status == PaymentStatus.PAGO
    assert p1.payment_date is not None
    assert p2.payment_date is not None
    uow.commit.assert_awaited_once()
    mov_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_lote_soma_correta(team_id):
    """Garante que o total é calculado com precisão Decimal, não float."""
    pagamentos = [_make_pagamento(team_id, v) for v in ["0.10", "0.20", "0.30"]]
    svc, _, _, _ = _make_service(pagamentos)

    dto = BaixaLoteDTO(pagamento_ids=[p.id for p in pagamentos], team_id=team_id)
    resultado = await svc.pay_lote(dto)

    assert resultado.valor_total == Decimal("0.60")


@pytest.mark.asyncio
async def test_pagamento_inexistente(team_id):
    """ID inexistente → DomainError, nenhuma alteração persistida."""
    id_inexistente = uuid4()
    svc, pag_repo, mov_repo, uow = _make_service([])  # repo retorna vazio

    dto = BaixaLoteDTO(pagamento_ids=[id_inexistente], team_id=team_id)
    with pytest.raises(DomainError, match="não encontrado"):
        await svc.pay_lote(dto)

    mov_repo.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_pagamento_de_outro_tenant(team_id, outro_team_id):
    """
    list_by_ids filtra por team_id no banco; pagamentos de outro tenant
    simplesmente não retornam, resultando em 'não encontrado'.
    """
    p_outro = _make_pagamento(outro_team_id, "100.00")
    # O repo já filtra — retorna lista vazia para o team_id correto
    svc, _, mov_repo, uow = _make_service([])

    dto = BaixaLoteDTO(pagamento_ids=[p_outro.id], team_id=team_id)
    with pytest.raises(DomainError, match="não encontrado"):
        await svc.pay_lote(dto)

    mov_repo.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_pagamento_ja_pago(team_id):
    """Pagamento com status PAGO → DomainError, rollback implícito (sem commit)."""
    p_pago = _make_pagamento(team_id, "100.00", status=PaymentStatus.PAGO)
    svc, _, mov_repo, uow = _make_service([p_pago])

    dto = BaixaLoteDTO(pagamento_ids=[p_pago.id], team_id=team_id)
    with pytest.raises(DomainError, match="já efetuado"):
        await svc.pay_lote(dto)

    mov_repo.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_lote_misto_um_pago_interrompe_tudo(team_id):
    """
    Lote com um pagamento válido e um já pago:
    nenhuma alteração deve ser persistida (operação atômica).
    """
    p_ok = _make_pagamento(team_id, "100.00")
    p_pago = _make_pagamento(team_id, "50.00", status=PaymentStatus.PAGO)
    svc, pag_repo, mov_repo, uow = _make_service([p_ok, p_pago])

    dto = BaixaLoteDTO(pagamento_ids=[p_ok.id, p_pago.id], team_id=team_id)
    with pytest.raises(DomainError, match="já efetuado"):
        await svc.pay_lote(dto)

    mov_repo.save.assert_not_awaited()
    uow.commit.assert_not_awaited()
    # p_ok não deve ter sido alterado
    assert p_ok.status == PaymentStatus.AGUARDANDO


@pytest.mark.asyncio
async def test_lista_vazia_rejeitada(team_id):
    """Lista de IDs vazia → DomainError sem tocar no banco."""
    svc, _, mov_repo, uow = _make_service([])
    dto = BaixaLoteDTO(pagamento_ids=[], team_id=team_id)

    with pytest.raises(DomainError, match="vazia"):
        await svc.pay_lote(dto)

    mov_repo.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_movimentacao_criada_com_lote_info(team_id):
    """Confirma que a movimentação gerada carrega o lote_info estruturado."""
    p1 = _make_pagamento(team_id, "300.00")
    p2 = _make_pagamento(team_id, "700.00")

    capturado: list[Movimentacao] = []

    async def capturar_save(mov):
        capturado.append(mov)
        mov.id = uuid4()
        return mov

    svc, _, mov_repo, _ = _make_service([p1, p2])
    mov_repo.save = AsyncMock(side_effect=capturar_save)

    dto = BaixaLoteDTO(pagamento_ids=[p1.id, p2.id], team_id=team_id)
    await svc.pay_lote(dto)

    assert len(capturado) == 1
    mov = capturado[0]
    assert mov.lote_info is not None
    assert len(mov.lote_info["lote_ids"]) == 2
    assert len(mov.lote_info["lote_detalhes"]) == 2
    assert mov.type == MovimentacaoTypes.SAIDA
    assert mov.valor.amount == Decimal("1000.00")


# ── testes auxiliares de formatação ───────────────────────────────────────────

def test_fmt_brl_simples():
    assert _fmt_brl(Decimal("1234.56")) == "R$ 1.234,56"


def test_fmt_brl_centavos():
    assert _fmt_brl(Decimal("0.10")) == "R$ 0,10"


def test_fmt_brl_milhar():
    assert _fmt_brl(Decimal("1000000.00")) == "R$ 1.000.000,00"


def test_descricao_contem_ids(team_id):
    p1 = _make_pagamento(team_id, "100.00")
    p2 = _make_pagamento(team_id, "200.00")
    total = Decimal("300.00")

    desc = _build_lote_descricao([p1, p2], total)

    assert str(p1.id) in desc
    assert str(p2.id) in desc
    assert "R$ 300,00" in desc
    assert "Baixa em lote" in desc


def test_descricao_resumida_para_lotes_grandes(team_id):
    """Lotes com mais de 50 itens devem usar descrição resumida."""
    pagamentos = [_make_pagamento(team_id, "1.00") for _ in range(60)]
    total = Decimal("60.00")

    desc = _build_lote_descricao(pagamentos, total)

    assert "mais 10 pagamento(s)" in desc


@pytest.mark.asyncio
async def test_delete_pagamento_aguardando_do_mesmo_tenant(team_id):
    """Pagamento pendente do tenant atual pode ser apagado."""
    pagamento = _make_pagamento(team_id)
    svc, pag_repo, _, uow = _make_service([pagamento])

    await svc.delete_pagamento(pagamento.id, team_id)

    pag_repo.get_by_id.assert_awaited_once_with(pagamento.id, team_id)
    pag_repo.delete_unpaid.assert_awaited_once_with(pagamento.id, team_id)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_pagamento_de_outro_tenant_nao_encontra(team_id, outro_team_id):
    """Busca do delete deve ser filtrada por tenant para nao vazar outro time."""
    pagamento_outro_tenant = _make_pagamento(outro_team_id)
    svc, pag_repo, _, uow = _make_service([pagamento_outro_tenant])

    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.delete_pagamento(pagamento_outro_tenant.id, team_id)

    pag_repo.get_by_id.assert_awaited_once_with(pagamento_outro_tenant.id, team_id)
    pag_repo.delete_unpaid.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_pagamento_pago_eh_bloqueado(team_id):
    """Pagamento ja pago nao pode ser apagado."""
    pagamento = _make_pagamento(team_id, status=PaymentStatus.PAGO)
    svc, pag_repo, _, uow = _make_service([pagamento])

    with pytest.raises(DomainError, match="j.* efetuado"):
        await svc.delete_pagamento(pagamento.id, team_id)

    pag_repo.delete_unpaid.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_pagamento_bloqueia_corrida_com_baixa(team_id):
    """Se o pagamento virar pago entre leitura e delete, a remocao deve falhar."""
    pagamento = _make_pagamento(team_id)
    svc, pag_repo, _, uow = _make_service([pagamento])
    pag_repo.delete_unpaid.return_value = False

    with pytest.raises(DomainError, match="j.* efetuado"):
        await svc.delete_pagamento(pagamento.id, team_id)

    pag_repo.delete_unpaid.assert_awaited_once_with(pagamento.id, team_id)
    uow.commit.assert_not_awaited()
