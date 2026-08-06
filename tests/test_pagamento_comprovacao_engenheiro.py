"""Visao do engenheiro sobre a movimentacao gerada pelo pagamento.

O caso de baixa em lote e o critico: a movimentacao consolidada contem dados de
pagamentos de terceiros e nao pode vazar.
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.services.financeiro_service import FinanceiroService
from app.domain.entities.financeiro import (
    MovClass, Movimentacao, MovimentacaoAttachment, MovimentacaoTypes,
    PagamentoAgendado, PaymentStatus,
)
from app.domain.entities.money import Money
from app.domain.entities.user import Roles
from app.domain.errors import DomainError


def _make_user(team_id, role=Roles.ENGENHEIRO, user_id=None):
    return SimpleNamespace(
        id=user_id or uuid4(), nome="Ana", role=role,
        team=SimpleNamespace(id=team_id),
    )


def _make_pagamento(team_id, created_by_user_id, status=PaymentStatus.PAGO):
    p = PagamentoAgendado(
        team_id=team_id, title="Servico eletrica", details="",
        valor=Money(Decimal("100.00")), data_agendada=datetime.now(timezone.utc),
        classe=MovClass.SERVICO,
    )
    p.id = uuid4()
    p.status = status
    p.created_by_user_id = created_by_user_id
    p.created_by_engineer = True
    return p


def _make_service(pagamentos, movimentacao=None, attachments=None):
    attachments = attachments or []

    pag_repo = AsyncMock()

    async def get_pagamento(pag_id, team_id=None):
        for p in pagamentos:
            if p.id == pag_id and (team_id is None or p.team_id == team_id):
                return p
        raise DomainError("Pagamento nao encontrado")

    pag_repo.get_by_id = AsyncMock(side_effect=get_pagamento)

    mov_repo = AsyncMock()
    mov_repo.get_by_pagamento = AsyncMock(return_value=movimentacao)

    mov_att_repo = AsyncMock()
    mov_att_repo.list_by_movimentacao = AsyncMock(return_value=attachments)

    return FinanceiroService(
        mov_repo=mov_repo, pagamento_repo=pag_repo,
        mov_attachment_repo=mov_att_repo, pagamento_attachment_repo=AsyncMock(),
        diarist_repo=AsyncMock(), uow=AsyncMock(),
    )


def _make_att(mov_id, team_id, file_name, kind="documento", origem=None):
    a = MovimentacaoAttachment(
        movimentacao_id=mov_id, team_id=team_id, file_path=f"x/{file_name}",
        file_name=file_name, content_type="application/pdf",
        kind=kind, origem_pagamento_id=origem,
    )
    a.id = uuid4()
    return a


@pytest.mark.asyncio
async def test_pagamento_aguardando_nao_tem_movimentacao(team_id):
    actor = _make_user(team_id)
    pagamento = _make_pagamento(team_id, actor.id, status=PaymentStatus.AGUARDANDO)
    svc = _make_service([pagamento], movimentacao=None)

    result = await svc.get_pagamento_comprovacao(pagamento.id, team_id, actor_user=actor)

    assert result.movimentacao is None
    assert result.attachments == []


@pytest.mark.asyncio
async def test_baixa_individual_devolve_tudo(team_id):
    actor = _make_user(team_id)
    pagamento = _make_pagamento(team_id, actor.id)
    mov = Movimentacao(
        team_id=team_id, title="Servico eletrica", type=MovimentacaoTypes.SAIDA,
        valor=Money(Decimal("100.00")), classe=MovClass.SERVICO,
        pagamento_id=pagamento.id,
    )
    mov.id = uuid4()
    atts = [
        _make_att(mov.id, team_id, "boleto.pdf", origem=pagamento.id),
        _make_att(mov.id, team_id, "comprovante.pdf", kind="comprovante"),
    ]
    svc = _make_service([pagamento], movimentacao=mov, attachments=atts)

    result = await svc.get_pagamento_comprovacao(pagamento.id, team_id, actor_user=actor)

    assert result.movimentacao.is_lote is False
    assert result.movimentacao.title == "Servico eletrica"
    assert result.movimentacao.valor == Decimal("100.00")
    assert {a.file_name for a in result.attachments} == {"boleto.pdf", "comprovante.pdf"}


@pytest.mark.asyncio
async def test_lote_nao_vaza_dados_de_terceiros(team_id):
    actor = _make_user(team_id)
    meu = _make_pagamento(team_id, actor.id)
    outro_id = uuid4()

    mov = Movimentacao(
        team_id=team_id,
        title="Baixa em lote de pagamentos:\n- Pagamento SIGILOSO de outro engenheiro",
        type=MovimentacaoTypes.SAIDA, valor=Money(Decimal("999.00")),
        classe=MovClass.OPERACIONAL,
        lote_info={"lote_ids": [str(meu.id), str(outro_id)], "lote_detalhes": []},
    )
    mov.id = uuid4()
    atts = [
        _make_att(mov.id, team_id, "meu_boleto.pdf", origem=meu.id),
        _make_att(mov.id, team_id, "boleto_alheio.pdf", origem=outro_id),
        _make_att(mov.id, team_id, "comprovante_lote.pdf", kind="comprovante"),
        _make_att(mov.id, team_id, "legado_sem_origem.pdf"),
    ]
    svc = _make_service([meu], movimentacao=mov, attachments=atts)

    result = await svc.get_pagamento_comprovacao(meu.id, team_id, actor_user=actor)

    assert result.movimentacao.is_lote is True
    assert "SIGILOSO" not in result.movimentacao.title
    assert "lote" in result.movimentacao.title.lower()
    # valor exibido e o do pagamento consultado, nao o total do lote
    assert result.movimentacao.valor == Decimal("100.00")
    nomes = {a.file_name for a in result.attachments}
    assert nomes == {"meu_boleto.pdf", "comprovante_lote.pdf"}


@pytest.mark.asyncio
async def test_engenheiro_nao_acessa_pagamento_de_outro(team_id):
    actor = _make_user(team_id)
    alheio = _make_pagamento(team_id, uuid4())
    svc = _make_service([alheio])

    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.get_pagamento_comprovacao(alheio.id, team_id, actor_user=actor)


@pytest.mark.asyncio
async def test_admin_acessa_qualquer_pagamento_do_time(team_id):
    admin = _make_user(team_id, role=Roles.ADMIN)
    pagamento = _make_pagamento(team_id, uuid4())
    mov = Movimentacao(
        team_id=team_id, title="Servico", type=MovimentacaoTypes.SAIDA,
        valor=Money(Decimal("100.00")), classe=MovClass.SERVICO,
        pagamento_id=pagamento.id,
    )
    mov.id = uuid4()
    svc = _make_service([pagamento], movimentacao=mov)

    result = await svc.get_pagamento_comprovacao(pagamento.id, team_id, actor_user=admin)

    assert result.movimentacao is not None
