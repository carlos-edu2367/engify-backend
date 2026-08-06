"""Testes da flag 'necessita de comprovante' e da marcacao de receipt_attached."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.financeiro import (
    MovClass, MovimentacaoAttachment, PagamentoAgendado, PaymentStatus,
)
from app.domain.entities.money import Money


def test_pagamento_tem_flags_de_comprovante_desligadas_por_padrao(team_id):
    p = PagamentoAgendado(
        team_id=team_id, title="X", details="", valor=Money(Decimal("10.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
    )
    assert p.requires_receipt is False
    assert p.receipt_attached is False


def test_pagamento_aceita_requires_receipt(team_id):
    p = PagamentoAgendado(
        team_id=team_id, title="X", details="", valor=Money(Decimal("10.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
        requires_receipt=True,
    )
    assert p.requires_receipt is True


def test_anexo_de_movimentacao_nasce_como_documento(team_id):
    a = MovimentacaoAttachment(
        movimentacao_id=uuid4(), team_id=team_id, file_path="p",
        file_name="n.pdf", content_type="application/pdf",
    )
    assert a.kind == "documento"
    assert a.origem_pagamento_id is None


def test_anexo_de_movimentacao_aceita_comprovante_e_origem(team_id):
    origem = uuid4()
    a = MovimentacaoAttachment(
        movimentacao_id=uuid4(), team_id=team_id, file_path="p",
        file_name="n.pdf", content_type="application/pdf",
        kind="comprovante", origem_pagamento_id=origem,
    )
    assert a.kind == "comprovante"
    assert a.origem_pagamento_id == origem


# ── marcacao de receipt_attached e copia na baixa ───────────────────────────────

from unittest.mock import AsyncMock

from app.application.dtos.financeiro import (
    AddMovimentacaoAttachmentDTO, BaixaLoteDTO,
)
from app.application.services.financeiro_service import FinanceiroService
from app.domain.entities.financeiro import Movimentacao, MovimentacaoTypes, PagamentoAttachment


def _make_pagamento(team_id, requires_receipt=False, status=PaymentStatus.AGUARDANDO):
    p = PagamentoAgendado(
        team_id=team_id, title="Servico", details="", valor=Money(Decimal("100.00")),
        data_agendada=datetime.now(timezone.utc), classe=MovClass.SERVICO,
        requires_receipt=requires_receipt,
    )
    p.id = uuid4()
    p.status = status
    return p


def _make_service(pagamentos=None, pag_attachments=None):
    pagamentos = pagamentos or []
    pag_attachments = pag_attachments or []
    salvos_mov_att = []

    pag_repo = AsyncMock()
    pag_repo.save = AsyncMock(side_effect=lambda p: p)
    pag_repo.list_by_ids = AsyncMock(
        side_effect=lambda ids, team_id: [p for p in pagamentos if p.id in ids]
    )
    pag_repo.get_by_id = AsyncMock(side_effect=lambda pid, tid=None: next(
        (p for p in pagamentos if p.id == pid), None
    ))

    pag_att_repo = AsyncMock()
    pag_att_repo.list_by_pagamento = AsyncMock(
        side_effect=lambda pid: [a for a in pag_attachments if a.pagamento_id == pid]
    )
    pag_att_repo.list_by_pagamentos = AsyncMock(
        side_effect=lambda pids: [a for a in pag_attachments if a.pagamento_id in pids]
    )

    mov_repo = AsyncMock()

    async def save_mov(m):
        if m.id is None:
            m.id = uuid4()
        return m

    mov_repo.save = AsyncMock(side_effect=save_mov)

    mov_att_repo = AsyncMock()

    async def save_mov_att(a):
        if a.id is None:
            a.id = uuid4()
        salvos_mov_att.append(a)
        return a

    mov_att_repo.save = AsyncMock(side_effect=save_mov_att)

    svc = FinanceiroService(
        mov_repo=mov_repo, pagamento_repo=pag_repo,
        mov_attachment_repo=mov_att_repo, pagamento_attachment_repo=pag_att_repo,
        diarist_repo=AsyncMock(), uow=AsyncMock(),
    )
    return svc, pag_repo, salvos_mov_att


@pytest.mark.asyncio
async def test_copia_de_anexo_marca_documento_e_origem(team_id):
    pagamento = _make_pagamento(team_id)
    anexo = PagamentoAttachment(
        pagamento_id=pagamento.id, team_id=team_id, file_path="pagamento/x/b.pdf",
        file_name="boleto.pdf", content_type="application/pdf",
    )
    anexo.id = uuid4()
    svc, _, salvos = _make_service([pagamento], [anexo])

    await svc.pay_pagamento(pagamento)

    assert len(salvos) == 1
    assert salvos[0].kind == "documento"
    assert salvos[0].origem_pagamento_id == pagamento.id


@pytest.mark.asyncio
async def test_comprovante_marca_receipt_attached_no_pagamento(team_id):
    pagamento = _make_pagamento(team_id, requires_receipt=True, status=PaymentStatus.PAGO)
    svc, pag_repo, _ = _make_service([pagamento])

    mov = Movimentacao(
        team_id=team_id, title="Saida", type=MovimentacaoTypes.SAIDA,
        valor=Money(Decimal("100.00")), classe=MovClass.SERVICO,
        pagamento_id=pagamento.id,
    )
    mov.id = uuid4()

    dto = AddMovimentacaoAttachmentDTO(
        file_path="financeiro/x/c.pdf", file_name="comprovante.pdf",
        content_type="application/pdf", kind="comprovante",
    )
    await svc.add_attachment(mov, dto)

    assert pagamento.receipt_attached is True


@pytest.mark.asyncio
async def test_documento_nao_marca_receipt_attached(team_id):
    pagamento = _make_pagamento(team_id, requires_receipt=True, status=PaymentStatus.PAGO)
    svc, _, _ = _make_service([pagamento])

    mov = Movimentacao(
        team_id=team_id, title="Saida", type=MovimentacaoTypes.SAIDA,
        valor=Money(Decimal("100.00")), classe=MovClass.SERVICO,
        pagamento_id=pagamento.id,
    )
    mov.id = uuid4()

    dto = AddMovimentacaoAttachmentDTO(
        file_path="financeiro/x/n.pdf", file_name="nota.pdf",
        content_type="application/pdf",
    )
    await svc.add_attachment(mov, dto)

    assert pagamento.receipt_attached is False


@pytest.mark.asyncio
async def test_comprovante_em_lote_marca_todos_os_pagamentos(team_id):
    p1 = _make_pagamento(team_id, requires_receipt=True, status=PaymentStatus.PAGO)
    p2 = _make_pagamento(team_id, requires_receipt=True, status=PaymentStatus.PAGO)
    svc, _, _ = _make_service([p1, p2])

    mov = Movimentacao(
        team_id=team_id, title="Lote", type=MovimentacaoTypes.SAIDA,
        valor=Money(Decimal("200.00")), classe=MovClass.OPERACIONAL,
        lote_info={"lote_ids": [str(p1.id), str(p2.id)], "lote_detalhes": []},
    )
    mov.id = uuid4()

    dto = AddMovimentacaoAttachmentDTO(
        file_path="financeiro/x/c.pdf", file_name="comprovante.pdf",
        content_type="application/pdf", kind="comprovante",
    )
    await svc.add_attachment(mov, dto)

    assert p1.receipt_attached is True
    assert p2.receipt_attached is True


@pytest.mark.asyncio
async def test_pay_lote_conta_pagamentos_que_pedem_comprovante(team_id):
    p1 = _make_pagamento(team_id, requires_receipt=True)
    p2 = _make_pagamento(team_id, requires_receipt=False)
    p3 = _make_pagamento(team_id, requires_receipt=True)
    svc, _, _ = _make_service([p1, p2, p3])

    result = await svc.pay_lote(
        BaixaLoteDTO(pagamento_ids=[p1.id, p2.id, p3.id], team_id=team_id)
    )

    assert result.quantidade == 3
    assert result.comprovante_pendente_count == 2
