"""Testes do FinanceiroService para os fluxos usados pelo Arky:
criacao em lote (atomica) e leitura escopada de atrasados/busca.
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.application.dtos.financeiro import CreatePagamentoDTO
from app.application.services.financeiro_service import FinanceiroService
from app.domain.entities.financeiro import MovClass
from app.domain.entities.user import Roles
from app.domain.errors import DomainError


def _make_user(team_id, role=Roles.FINANCEIRO, nome="Fin", user_id=None):
    return SimpleNamespace(id=user_id or uuid4(), nome=nome, role=role,
                           team=SimpleNamespace(id=team_id))


def _make_service():
    pag_repo = AsyncMock()
    pag_repo.save = AsyncMock(side_effect=lambda p: p)
    pag_repo.list_overdue = AsyncMock(return_value=[])
    pag_repo.search = AsyncMock(return_value=[])
    diarist_repo = AsyncMock()
    diarist_repo.get_by_id = AsyncMock(side_effect=DomainError("nao encontrado"))
    svc = FinanceiroService(
        mov_repo=AsyncMock(),
        pagamento_repo=pag_repo,
        mov_attachment_repo=AsyncMock(),
        diarist_repo=diarist_repo,
        uow=AsyncMock(),
    )
    return svc, pag_repo


def _dto(title="Pgto", payment_cod="pix-1", classe=MovClass.MATERIAL):
    return CreatePagamentoDTO(
        title=title, details="d", valor=Decimal("120.00"), classe=classe,
        data_agendada=datetime.now(timezone.utc), payment_cod=payment_cod,
    )


@pytest.mark.asyncio
async def test_create_pagamentos_batch_atomic_single_commit(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.FINANCEIRO)

    criados = await svc.create_pagamentos(
        [_dto("A"), _dto("B"), _dto("C")], team_id, actor_user=actor
    )

    assert len(criados) == 3
    assert pag_repo.save.await_count == 3
    svc.uow.commit.assert_awaited_once()  # commit unico = atomicidade
    assert all(p.created_by_user_id == actor.id for p in criados)


@pytest.mark.asyncio
async def test_create_pagamentos_empty_list_rejected(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id)
    with pytest.raises(DomainError, match="vazia"):
        await svc.create_pagamentos([], team_id, actor_user=actor)
    pag_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_pagamentos_engineer_missing_code_fails_before_any_save(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)

    # Segundo item sem codigo -> falha total, nada salvo, nada commitado.
    with pytest.raises(DomainError, match="codigo de pagamento"):
        await svc.create_pagamentos(
            [_dto("A", payment_cod="pix-1"), _dto("B", payment_cod="  ")],
            team_id, actor_user=actor,
        )
    pag_repo.save.assert_not_awaited()
    svc.uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_pagamentos_stamps_engineer_authorship(team_id):
    svc, _ = _make_service()
    actor = _make_user(team_id, role=Roles.ENGENHEIRO, nome="Ana Eng")
    criados = await svc.create_pagamentos([_dto("A")], team_id, actor_user=actor)
    p = criados[0]
    assert p.created_by_engineer is True
    assert p.created_by_role == "engenheiro"
    assert p.created_by_name == "Ana Eng"


@pytest.mark.asyncio
async def test_overdue_scoped_to_creator_for_engineer(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)
    await svc.list_pagamentos_overdue(team_id, actor_user=actor, limit=10)
    # owner_id (4o argumento posicional) deve ser o id do engenheiro
    assert pag_repo.list_overdue.await_args.args[3] == actor.id


@pytest.mark.asyncio
async def test_overdue_not_scoped_for_admin(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.ADMIN)
    await svc.list_pagamentos_overdue(team_id, actor_user=actor, limit=10)
    assert pag_repo.list_overdue.await_args.args[3] is None


@pytest.mark.asyncio
async def test_search_scoped_to_creator_for_engineer(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.ENGENHEIRO)
    await svc.search_pagamentos(team_id, "pedro", actor_user=actor, limit=5)
    assert pag_repo.search.await_args.args[3] == actor.id


@pytest.mark.asyncio
async def test_search_not_scoped_for_financeiro(team_id):
    svc, pag_repo = _make_service()
    actor = _make_user(team_id, role=Roles.FINANCEIRO)
    await svc.search_pagamentos(team_id, "pedro", actor_user=actor, limit=5)
    assert pag_repo.search.await_args.args[3] is None
