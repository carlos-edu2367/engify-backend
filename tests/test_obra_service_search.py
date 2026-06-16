from uuid import uuid4

import pytest

from app.application.services.obra_service import ObraService, CategoriaObraService
from app.domain.entities.obra import Status


class _FakeObraRepo:
    def __init__(self):
        self.list_calls = []
        self.count_calls = []
        self.status_list_calls = []
        self.status_count_calls = []
        self.categoria_list_calls = []
        self.categoria_count_calls = []

    async def get_by_team(self, team_id, page, limit, search=None):
        self.list_calls.append((team_id, page, limit, search))
        return []

    async def count_by_team(self, team_id, search=None):
        self.count_calls.append((team_id, search))
        return 0

    async def get_by_status(self, team_id, status, limit, page, search=None):
        self.status_list_calls.append((team_id, status, limit, page, search))
        return []

    async def count_by_status(self, team_id, status, search=None):
        self.status_count_calls.append((team_id, status, search))
        return 0

    async def get_by_categoria(self, categoria_id, team_id, page, limit, search=None):
        self.categoria_list_calls.append((categoria_id, team_id, page, limit, search))
        return []

    async def count_by_categoria(self, categoria_id, team_id, search=None):
        self.categoria_count_calls.append((categoria_id, team_id, search))
        return 0


class _FakeUow:
    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_list_obras_forwards_search_to_repo():
    repo = _FakeObraRepo()
    service = ObraService(repo, _FakeUow())
    team_id = uuid4()

    await service.list_obras(team_id, page=1, limit=50, search="Reforma")

    assert repo.list_calls == [(team_id, 1, 50, "Reforma")]


@pytest.mark.asyncio
async def test_count_obras_forwards_search_to_repo():
    repo = _FakeObraRepo()
    service = ObraService(repo, _FakeUow())
    team_id = uuid4()

    await service.count_obras(team_id, search="Reforma")

    assert repo.count_calls == [(team_id, "Reforma")]


@pytest.mark.asyncio
async def test_list_by_status_forwards_search_to_repo():
    repo = _FakeObraRepo()
    service = ObraService(repo, _FakeUow())
    team_id = uuid4()

    await service.list_by_status(team_id, Status.EM_ANDAMENTO, page=1, limit=50, search="Casa")

    assert repo.status_list_calls == [(team_id, Status.EM_ANDAMENTO, 50, 1, "Casa")]


@pytest.mark.asyncio
async def test_count_by_status_forwards_search_to_repo():
    repo = _FakeObraRepo()
    service = ObraService(repo, _FakeUow())
    team_id = uuid4()

    await service.count_by_status(team_id, Status.EM_ANDAMENTO, search="Casa")

    assert repo.status_count_calls == [(team_id, Status.EM_ANDAMENTO, "Casa")]


@pytest.mark.asyncio
async def test_list_obras_by_categoria_forwards_search_to_repo():
    repo = _FakeObraRepo()
    service = CategoriaObraService(categoria_repo=None, obra_repo=repo, uow=_FakeUow())
    team_id = uuid4()
    categoria_id = uuid4()

    await service.list_obras_by_categoria(categoria_id, team_id, page=1, limit=50, search="Casa")

    assert repo.categoria_list_calls == [(categoria_id, team_id, 1, 50, "Casa")]


@pytest.mark.asyncio
async def test_count_obras_by_categoria_forwards_search_to_repo():
    repo = _FakeObraRepo()
    service = CategoriaObraService(categoria_repo=None, obra_repo=repo, uow=_FakeUow())
    team_id = uuid4()
    categoria_id = uuid4()

    await service.count_obras_by_categoria(categoria_id, team_id, search="Casa")

    assert repo.categoria_count_calls == [(categoria_id, team_id, "Casa")]
