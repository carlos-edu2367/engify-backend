import pytest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.dtos.financeiro import CreatePagamentoDTO, EditPagamentoDTO, PagamentoFiltersDTO
from app.application.services.financeiro_service import FinanceiroService
from app.domain.entities.financeiro import MovClass, PagamentoAgendado, PaymentStatus
from app.domain.entities.money import Money
from app.domain.entities.user import Roles
from app.domain.errors import DomainError


def _make_user(team_id, role=Roles.ENGENHEIRO, nome="Engenheiro", user_id=None):
    return SimpleNamespace(id=user_id or uuid4(), nome=nome, role=role, team=SimpleNamespace(id=team_id))


def _make_pagamento(team_id, created_by_user_id=None, status=PaymentStatus.AGUARDANDO, payment_cod="pix-123"):
    p = object.__new__(PagamentoAgendado)
    p.id = uuid4()
    p.team_id = team_id
    p.title = "Servico"
    p.details = "Detalhe"
    p.valor = Money(Decimal("190.50"))
    p.classe = MovClass.SERVICO
    p.data_agendada = datetime.now(timezone.utc)
    p.payment_cod = payment_cod
    p.pix_copy_and_past = None
    p.status = status
    p.payment_date = None
    p.obra_id = None
    p.diarist_id = None
    p.created_by_user_id = created_by_user_id
    p.created_by_role = Roles.ENGENHEIRO.value if created_by_user_id else None
    p.created_by_name = "Engenheiro" if created_by_user_id else None
    p.created_by_engineer = created_by_user_id is not None
    p.created_at = datetime.now(timezone.utc)
    return p


def _make_service(pagamentos=None):
    pagamentos = pagamentos or []
    pag_repo = AsyncMock()
    pag_repo.save = AsyncMock(side_effect=lambda p: p)
    pag_repo.list_by_team = AsyncMock(return_value=pagamentos)
    pag_repo.count_by_team = AsyncMock(return_value=len(pagamentos))
    pag_repo.delete_unpaid = AsyncMock(return_value=True)

    async def get_by_id(pag_id, team_id=None):
        for pagamento in pagamentos:
            if pagamento.id == pag_id and (team_id is None or pagamento.team_id == team_id):
                return pagamento
        raise DomainError("Pagamento nao encontrado")

    pag_repo.get_by_id = AsyncMock(side_effect=get_by_id)

    svc = FinanceiroService(
        mov_repo=AsyncMock(),
        pagamento_repo=pag_repo,
        mov_attachment_repo=AsyncMock(),
        diarist_repo=AsyncMock(),
        uow=AsyncMock(),
    )
    return svc, pag_repo


def _create_dto(payment_cod="pix-123"):
    return CreatePagamentoDTO(
        title="Pagamento",
        details="Detalhes",
        valor=Decimal("190.50"),
        classe=MovClass.SERVICO,
        data_agendada=datetime.now(timezone.utc),
        payment_cod=payment_cod,
    )


@pytest.mark.asyncio
async def test_engineer_create_requires_payment_code(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)

    with pytest.raises(DomainError, match="codigo de pagamento"):
        await svc.create_pagamento(_create_dto(payment_cod="   "), team_id, actor_user=actor)

    pag_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_engineer_create_stamps_creator_metadata(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.ENGENHEIRO, nome="Ana Eng")

    pagamento = await svc.create_pagamento(_create_dto(), team_id, actor_user=actor)

    assert pagamento.created_by_user_id == actor.id
    assert pagamento.created_by_role == "engenheiro"
    assert pagamento.created_by_name == "Ana Eng"
    assert pagamento.created_by_engineer is True
    pag_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_financeiro_create_can_keep_payment_code_empty(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.FINANCEIRO, nome="Financeiro")

    pagamento = await svc.create_pagamento(_create_dto(payment_cod=None), team_id, actor_user=actor)

    assert pagamento.payment_cod is None
    assert pagamento.created_by_engineer is False
    assert pagamento.created_by_user_id == actor.id
    pag_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_engineer_list_and_count_are_scoped_to_creator(team_id):
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)
    svc, pag_repo = _make_service([_make_pagamento(team_id, actor.id)])

    await svc.list_pagamentos(team_id, 1, 50, PagamentoFiltersDTO(), actor_user=actor)
    await svc.count_pagamentos(team_id, PagamentoFiltersDTO(), actor_user=actor)

    list_filters = pag_repo.list_by_team.await_args.args[3]
    count_filters = pag_repo.count_by_team.await_args.args[1]
    assert list_filters.created_by_user_id == actor.id
    assert count_filters.created_by_user_id == actor.id


@pytest.mark.asyncio
async def test_admin_list_does_not_scope_by_creator(team_id):
    actor = _make_user(team_id, role=Roles.ADMIN)
    svc, pag_repo = _make_service([_make_pagamento(team_id)])

    await svc.list_pagamentos(team_id, 1, 50, PagamentoFiltersDTO(), actor_user=actor)

    filters = pag_repo.list_by_team.await_args.args[3]
    assert filters.created_by_user_id is None


@pytest.mark.asyncio
async def test_engineer_cannot_get_edit_or_delete_other_user_payment(team_id):
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)
    pagamento = _make_pagamento(team_id, created_by_user_id=uuid4())
    svc, pag_repo = _make_service([pagamento])

    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.get_pagamento(pagamento.id, team_id, actor_user=actor)
    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.edit_pagamento(pagamento, EditPagamentoDTO(title="Novo"), actor_user=actor)
    with pytest.raises(DomainError, match="nao encontrado"):
        await svc.delete_pagamento(pagamento.id, team_id, actor_user=actor)

    pag_repo.delete_unpaid.assert_not_awaited()


@pytest.mark.asyncio
async def test_engineer_cannot_edit_or_delete_paid_payment(team_id):
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)
    pagamento = _make_pagamento(team_id, created_by_user_id=actor.id, status=PaymentStatus.PAGO)
    svc, pag_repo = _make_service([pagamento])

    with pytest.raises(DomainError, match="ja foi efetuado"):
        await svc.edit_pagamento(pagamento, EditPagamentoDTO(title="Novo"), actor_user=actor)
    with pytest.raises(DomainError, match="ja foi efetuado"):
        await svc.delete_pagamento(pagamento.id, team_id, actor_user=actor)

    pag_repo.delete_unpaid.assert_not_awaited()


@pytest.mark.asyncio
async def test_engineer_delete_uses_owner_in_conditioned_delete(team_id):
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)
    pagamento = _make_pagamento(team_id, created_by_user_id=actor.id)
    svc, pag_repo = _make_service([pagamento])

    await svc.delete_pagamento(pagamento.id, team_id, actor_user=actor)

    pag_repo.delete_unpaid.assert_awaited_once_with(pagamento.id, team_id, actor.id)
