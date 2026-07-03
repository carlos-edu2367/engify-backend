"""
Reproduz a race condition entre uma listagem de pagamentos em andamento
(cache miss -> query -> set) e uma invalidacao concorrente disparada por
create/edit/delete. Sem protecao, a listagem em andamento grava no cache
um resultado desatualizado *depois* da invalidacao ja ter rodado, deixando
o cache com dado stale pelo TTL inteiro (5min).
"""
import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.http.routers import financeiro as financeiro_router
from app.http.dependencies.pagination import PaginationParams
from app.application.dtos.financeiro import PagamentoFiltersDTO
from app.http.schemas.financeiro import PagamentoReadResponse
from app.domain.entities.financeiro import MovClass, PaymentStatus


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def incr(self, key):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = str(value)
        return value

    async def delete(self, key):
        self.store.pop(key, None)

    async def scan_iter(self, match=None, count=None):
        prefix = match.rstrip("*")
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key


class FakeFinanceiroService:
    """Simula a 1a chamada de list_pagamentos demorando (query lenta),
    dando tempo da invalidacao concorrente rodar antes dela terminar."""

    def __init__(self, responses, query_started=None, wait_for=None):
        self._responses = responses
        self.list_calls = 0
        self.query_started = query_started
        self.wait_for = wait_for

    def get_pagamento_filters_for_actor(self, filters, user, scope):
        return filters or PagamentoFiltersDTO()

    async def list_pagamentos(self, team_id, page, limit, filters, actor_user=None, scope="mine"):
        idx = self.list_calls
        self.list_calls += 1
        if idx == 0 and self.query_started is not None:
            self.query_started.set()
            await self.wait_for.wait()
        return self._responses[idx]

    async def count_pagamentos(self, team_id, filters, actor_user=None, scope="mine"):
        return len(self._responses[self.list_calls - 1])


def _make_user(team_id):
    return SimpleNamespace(team=SimpleNamespace(id=team_id))


def _make_pagamento(title):
    return PagamentoReadResponse(
        id=uuid4(),
        title=title,
        details="",
        valor=Decimal("100.00"),
        classe=MovClass.SERVICO,
        status=PaymentStatus.AGUARDANDO,
        data_agendada="2026-07-10T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_stale_list_write_after_concurrent_invalidation_does_not_poison_cache(monkeypatch):
    team_id = uuid4()
    user = _make_user(team_id)
    pagination = PaginationParams(page=1, limit=50)
    filters = PagamentoFiltersDTO()

    fake_redis = FakeRedis()
    monkeypatch.setattr(financeiro_router, "get_redis", lambda: fake_redis)

    query_started = asyncio.Event()
    invalidation_done = asyncio.Event()

    stale_item = _make_pagamento("Pagamento antigo")
    fresh_item = _make_pagamento("Pagamento novo")
    svc = FakeFinanceiroService(
        responses=[[stale_item], [fresh_item]],
        query_started=query_started,
        wait_for=invalidation_done,
    )

    async def run_list():
        return await financeiro_router.list_pagamentos(
            user=user, pagination=pagination, filters=filters, scope="all", svc=svc,
        )

    async def run_concurrent_create_invalidation():
        # Espera a listagem comecar a query (miss de cache confirmado)
        # antes de simular o create/edit/delete que invalida o cache.
        await query_started.wait()
        await financeiro_router._invalidate_pagamentos_cache(fake_redis, team_id)
        invalidation_done.set()

    await asyncio.gather(run_list(), run_concurrent_create_invalidation())

    # Uma nova requisicao de listagem, feita apos a invalidacao, nao pode
    # ver o dado stale que a listagem concorrente gravou no cache depois
    # da invalidacao ja ter rodado.
    fresh_result = await financeiro_router.list_pagamentos(
        user=user, pagination=pagination, filters=filters, scope="all", svc=svc,
    )

    assert svc.list_calls == 2, "listagem pos-invalidacao deveria ir ao banco, nao ao cache poluido"
    assert fresh_result.items[0].title == "Pagamento novo"


@pytest.mark.asyncio
async def test_list_pagamentos_still_uses_cache_without_concurrent_writes(monkeypatch):
    team_id = uuid4()
    user = _make_user(team_id)
    pagination = PaginationParams(page=1, limit=50)
    filters = PagamentoFiltersDTO()

    fake_redis = FakeRedis()
    monkeypatch.setattr(financeiro_router, "get_redis", lambda: fake_redis)

    item = _make_pagamento("Pagamento unico")
    svc = FakeFinanceiroService(responses=[[item], [item]])

    await financeiro_router.list_pagamentos(
        user=user, pagination=pagination, filters=filters, scope="all", svc=svc,
    )
    await financeiro_router.list_pagamentos(
        user=user, pagination=pagination, filters=filters, scope="all", svc=svc,
    )

    assert svc.list_calls == 1, "segunda chamada sem invalidacao deveria vir do cache"
