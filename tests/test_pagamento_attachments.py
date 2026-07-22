"""
Testes para anexos de pagamento agendado: CRUD com trava de ownership/status,
e cópia para a Movimentação gerada na baixa (individual e em lote).
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.dtos.financeiro import AddPagamentoAttachmentDTO, BaixaLoteDTO
from app.application.services.financeiro_service import FinanceiroService
from app.domain.entities.financeiro import (
    MovClass, PagamentoAgendado, PagamentoAttachment, PaymentStatus,
)
from app.domain.entities.money import Money
from app.domain.entities.user import Roles
from app.domain.errors import DomainError


def _make_user(team_id, role=Roles.ENGENHEIRO, user_id=None):
    return SimpleNamespace(id=user_id or uuid4(), nome="Ana", role=role, team=SimpleNamespace(id=team_id))


def _make_pagamento(team_id, created_by_user_id=None, status=PaymentStatus.AGUARDANDO):
    p = object.__new__(PagamentoAgendado)
    p.id = uuid4()
    p.team_id = team_id
    p.title = "Servico"
    p.details = "Detalhe"
    p.valor = Money(Decimal("190.50"))
    p.classe = MovClass.SERVICO
    p.data_agendada = datetime.now(timezone.utc)
    p.payment_cod = "pix-123"
    p.pix_copy_and_past = None
    p.status = status
    p.payment_date = None
    p.obra_id = None
    p.diarist_id = None
    p.created_by_user_id = created_by_user_id
    p.created_by_role = Roles.ENGENHEIRO.value if created_by_user_id else None
    p.created_by_name = "Ana" if created_by_user_id else None
    p.created_by_engineer = created_by_user_id is not None
    p.created_at = datetime.now(timezone.utc)
    return p


def _make_attachment(pagamento_id, team_id, file_name="nota.pdf"):
    return PagamentoAttachment(
        pagamento_id=pagamento_id, team_id=team_id,
        file_path=f"pagamento/{pagamento_id}/{uuid4()}.pdf",
        file_name=file_name, content_type="application/pdf",
    )


def _make_service(pagamentos=None, attachments=None):
    pagamentos = pagamentos or []
    attachments = attachments if attachments is not None else []

    pag_repo = AsyncMock()

    async def get_pagamento_by_id(pag_id, team_id=None):
        for p in pagamentos:
            if p.id == pag_id and (team_id is None or p.team_id == team_id):
                return p
        raise DomainError("Pagamento nao encontrado")

    pag_repo.get_by_id = AsyncMock(side_effect=get_pagamento_by_id)
    pag_repo.list_by_ids = AsyncMock(side_effect=lambda ids, team_id: [
        p for p in pagamentos if p.id in ids and p.team_id == team_id
    ])
    pag_repo.save = AsyncMock(side_effect=lambda p: p)

    pag_att_repo = AsyncMock()

    async def get_attachment_by_id(att_id):
        for a in attachments:
            if a.id == att_id:
                return a
        raise DomainError("Anexo nao encontrado")

    pag_att_repo.get_by_id = AsyncMock(side_effect=get_attachment_by_id)
    pag_att_repo.list_by_pagamento = AsyncMock(
        side_effect=lambda pid: [a for a in attachments if a.pagamento_id == pid and not a.is_deleted]
    )
    pag_att_repo.list_by_pagamentos = AsyncMock(
        side_effect=lambda pids: [a for a in attachments if a.pagamento_id in pids and not a.is_deleted]
    )

    async def save_attachment(a):
        if a.id is None:
            a.id = uuid4()
            attachments.append(a)
        return a

    pag_att_repo.save = AsyncMock(side_effect=save_attachment)

    mov_repo = AsyncMock()
    mov_att_repo = AsyncMock()
    mov_att_repo.save = AsyncMock(side_effect=lambda a: a)

    async def save_mov(m):
        m.id = uuid4()
        return m

    mov_repo.save = AsyncMock(side_effect=save_mov)

    svc = FinanceiroService(
        mov_repo=mov_repo,
        pagamento_repo=pag_repo,
        mov_attachment_repo=mov_att_repo,
        pagamento_attachment_repo=pag_att_repo,
        diarist_repo=AsyncMock(),
        uow=AsyncMock(),
    )
    return svc, pag_repo, pag_att_repo, mov_repo, mov_att_repo


# ── add/list/delete ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_engineer_can_attach_to_own_pagamento(team_id):
    actor = _make_user(team_id)
    pagamento = _make_pagamento(team_id, created_by_user_id=actor.id)
    svc, *_ = _make_service([pagamento])

    pag = await svc.get_pagamento(pagamento.id, team_id, actor_user=actor)
    dto = AddPagamentoAttachmentDTO(file_path="pagamento/x/y.pdf", file_name="nota.pdf", content_type="application/pdf")
    att = await svc.add_pagamento_attachment(pag, dto)

    assert att.pagamento_id == pagamento.id
    assert att.file_name == "nota.pdf"


@pytest.mark.asyncio
async def test_engineer_cannot_attach_to_other_engineer_pagamento(team_id):
    actor = _make_user(team_id)
    pagamento = _make_pagamento(team_id, created_by_user_id=uuid4())
    svc, *_ = _make_service([pagamento])

    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.get_pagamento(pagamento.id, team_id, actor_user=actor)


@pytest.mark.asyncio
async def test_cannot_attach_to_paid_pagamento(team_id):
    actor = _make_user(team_id)
    pagamento = _make_pagamento(team_id, created_by_user_id=actor.id, status=PaymentStatus.PAGO)
    svc, *_ = _make_service([pagamento])

    dto = AddPagamentoAttachmentDTO(file_path="p", file_name="n.pdf", content_type="application/pdf")
    with pytest.raises(DomainError, match="ja foi efetuado"):
        await svc.add_pagamento_attachment(pagamento, dto)


@pytest.mark.asyncio
async def test_delete_attachment_removes_it_from_list(team_id):
    actor = _make_user(team_id)
    pagamento = _make_pagamento(team_id, created_by_user_id=actor.id)
    attachment = _make_attachment(pagamento.id, team_id)
    attachment.id = uuid4()
    svc, *_ = _make_service([pagamento], [attachment])

    await svc.delete_pagamento_attachment(attachment.id, pagamento)

    assert attachment.is_deleted is True
    remaining = await svc.get_pagamento_attachments(pagamento.id)
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_attachment_from_wrong_pagamento_rejected(team_id):
    pagamento_a = _make_pagamento(team_id, created_by_user_id=uuid4())
    pagamento_b = _make_pagamento(team_id, created_by_user_id=uuid4())
    attachment = _make_attachment(pagamento_a.id, team_id)
    attachment.id = uuid4()
    svc, *_ = _make_service([pagamento_a, pagamento_b], [attachment])

    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.delete_pagamento_attachment(attachment.id, pagamento_b)


@pytest.mark.asyncio
async def test_cannot_delete_attachment_of_paid_pagamento(team_id):
    pagamento = _make_pagamento(team_id, created_by_user_id=uuid4(), status=PaymentStatus.PAGO)
    attachment = _make_attachment(pagamento.id, team_id)
    attachment.id = uuid4()
    svc, *_ = _make_service([pagamento], [attachment])

    with pytest.raises(DomainError, match="ja foi efetuado"):
        await svc.delete_pagamento_attachment(attachment.id, pagamento)


# ── carry-over na baixa ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pay_pagamento_copies_attachments_to_movimentacao(team_id):
    pagamento = _make_pagamento(team_id, created_by_user_id=uuid4())
    attachment = _make_attachment(pagamento.id, team_id)
    attachment.id = uuid4()
    svc, _, _, mov_repo, mov_att_repo = _make_service([pagamento], [attachment])

    mov = await svc.pay_pagamento(pagamento)

    mov_att_repo.save.assert_awaited_once()
    copia = mov_att_repo.save.await_args.args[0]
    assert copia.movimentacao_id == mov.id
    assert copia.file_path == attachment.file_path
    assert copia.file_name == attachment.file_name


@pytest.mark.asyncio
async def test_pay_pagamento_sem_anexos_nao_copia_nada(team_id):
    pagamento = _make_pagamento(team_id, created_by_user_id=uuid4())
    svc, _, _, mov_repo, mov_att_repo = _make_service([pagamento])

    await svc.pay_pagamento(pagamento)

    mov_att_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_pay_pagamento_nao_copia_anexo_removido(team_id):
    pagamento = _make_pagamento(team_id, created_by_user_id=uuid4())
    attachment = _make_attachment(pagamento.id, team_id)
    attachment.id = uuid4()
    attachment.is_deleted = True
    svc, _, _, mov_repo, mov_att_repo = _make_service([pagamento], [attachment])

    await svc.pay_pagamento(pagamento)

    mov_att_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_pay_lote_copia_anexos_de_todos_os_pagamentos(team_id):
    p1 = _make_pagamento(team_id, created_by_user_id=uuid4())
    p2 = _make_pagamento(team_id, created_by_user_id=uuid4())
    att1 = _make_attachment(p1.id, team_id, "boleto1.pdf")
    att1.id = uuid4()
    att2 = _make_attachment(p2.id, team_id, "boleto2.pdf")
    att2.id = uuid4()
    svc, _, _, mov_repo, mov_att_repo = _make_service([p1, p2], [att1, att2])

    dto = BaixaLoteDTO(pagamento_ids=[p1.id, p2.id], team_id=team_id)
    await svc.pay_lote(dto)

    assert mov_att_repo.save.await_count == 2
    nomes_copiados = {c.args[0].file_name for c in mov_att_repo.save.await_args_list}
    assert nomes_copiados == {"boleto1.pdf", "boleto2.pdf"}
