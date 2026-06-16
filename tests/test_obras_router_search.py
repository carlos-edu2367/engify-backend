from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.http.routers import obras as obras_router
from app.http.dependencies.pagination import PaginationParams


class FakeRedis:
    def __init__(self):
        self.get_calls = 0
        self.set_calls = 0
        self.stored = {}

    async def get(self, key):
        self.get_calls += 1
        return self.stored.get(key)

    async def set(self, key, value, ex=None):
        self.set_calls += 1
        self.stored[key] = value


class FakeObraService:
    def __init__(self, obras, total):
        self.obras = obras
        self.total = total
        self.list_calls = []
        self.count_calls = []
        self.status_list_calls = []
        self.status_count_calls = []

    async def list_obras(self, team_id, page, limit, search=None):
        self.list_calls.append((team_id, page, limit, search))
        return self.obras

    async def count_obras(self, team_id, search=None):
        self.count_calls.append((team_id, search))
        return self.total

    async def list_by_status(self, team_id, status, page, limit, search=None):
        self.status_list_calls.append((team_id, status, page, limit, search))
        return self.obras

    async def count_by_status(self, team_id, status, search=None):
        self.status_count_calls.append((team_id, status, search))
        return self.total


def _make_user(team_id):
    return SimpleNamespace(team=SimpleNamespace(id=team_id))


def _make_obra(team_id, title="Reforma Sede"):
    from app.domain.entities.obra import Obra
    return Obra(
        title=title,
        team_id=team_id,
        responsavel_id=uuid4(),
        description=None,
        id=uuid4(),
    )


@pytest.mark.asyncio
async def test_list_obras_with_search_bypasses_cache(monkeypatch):
    team_id = uuid4()
    user = _make_user(team_id)
    obra = _make_obra(team_id)
    svc = FakeObraService([obra], total=1)
    fake_redis = FakeRedis()
    monkeypatch.setattr(obras_router, "get_redis", lambda: fake_redis)

    result = await obras_router.list_obras(
        user=user,
        pagination=PaginationParams(page=1, limit=50),
        svc=svc,
        status="all",
        search="Reforma",
    )

    assert svc.list_calls == [(team_id, 1, 50, "Reforma")]
    assert fake_redis.get_calls == 0
    assert fake_redis.set_calls == 0
    assert result.items[0].title == "Reforma Sede"


@pytest.mark.asyncio
async def test_list_obras_without_search_uses_cache(monkeypatch):
    team_id = uuid4()
    user = _make_user(team_id)
    obra = _make_obra(team_id)
    svc = FakeObraService([obra], total=1)
    fake_redis = FakeRedis()
    monkeypatch.setattr(obras_router, "get_redis", lambda: fake_redis)

    await obras_router.list_obras(
        user=user,
        pagination=PaginationParams(page=1, limit=50),
        svc=svc,
        status="all",
        search=None,
    )

    assert fake_redis.set_calls == 1


@pytest.mark.asyncio
async def test_list_obras_with_status_and_search_bypasses_cache_and_forwards_both(monkeypatch):
    team_id = uuid4()
    user = _make_user(team_id)
    obra = _make_obra(team_id)
    svc = FakeObraService([obra], total=1)
    fake_redis = FakeRedis()
    monkeypatch.setattr(obras_router, "get_redis", lambda: fake_redis)

    from app.domain.entities.obra import Status

    result = await obras_router.list_obras(
        user=user,
        pagination=PaginationParams(page=1, limit=50),
        svc=svc,
        status="em_andamento",
        search="Reforma",
    )

    assert svc.status_list_calls == [(team_id, Status.EM_ANDAMENTO, 1, 50, "Reforma")]
    assert svc.status_count_calls == [(team_id, Status.EM_ANDAMENTO, "Reforma")]
    assert svc.list_calls == []
    assert svc.count_calls == []
    assert fake_redis.get_calls == 0
    assert fake_redis.set_calls == 0
    assert result.items[0].title == "Reforma Sede"
