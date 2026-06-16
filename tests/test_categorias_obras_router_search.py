from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.domain.errors import DomainError
from app.http.routers import categorias_obras as categorias_router
from app.http.dependencies.pagination import PaginationParams


class FakeCategoriaService:
    def __init__(self, obras, total):
        self.obras = obras
        self.total = total
        self.list_calls = []

    async def get_categoria(self, categoria_id, team_id):
        return SimpleNamespace(id=categoria_id, team_id=team_id)

    async def list_obras_by_categoria(self, categoria_id, team_id, page, limit, search=None):
        self.list_calls.append((categoria_id, team_id, page, limit, search))
        return self.obras

    async def count_obras_by_categoria(self, categoria_id, team_id, search=None):
        return self.total


class FakeCategoriaServiceNotFound(FakeCategoriaService):
    async def get_categoria(self, categoria_id, team_id):
        raise DomainError("Categoria não encontrada")


def _make_obra(team_id, title="Casa Azul"):
    from app.domain.entities.obra import Obra
    return Obra(title=title, team_id=team_id, responsavel_id=uuid4(), description=None, id=uuid4())


@pytest.mark.asyncio
async def test_list_obras_by_categoria_forwards_search():
    team_id = uuid4()
    categoria_id = uuid4()
    user = SimpleNamespace(team=SimpleNamespace(id=team_id))
    obra = _make_obra(team_id)
    svc = FakeCategoriaService([obra], total=1)

    result = await categorias_router.list_obras_by_categoria(
        categoria_id=categoria_id,
        user=user,
        pagination=PaginationParams(page=1, limit=50),
        svc=svc,
        search="Azul",
    )

    assert svc.list_calls == [(categoria_id, team_id, 1, 50, "Azul")]
    assert result.items[0].title == "Casa Azul"


@pytest.mark.asyncio
async def test_list_obras_by_categoria_404_when_categoria_missing():
    team_id = uuid4()
    categoria_id = uuid4()
    user = SimpleNamespace(team=SimpleNamespace(id=team_id))
    svc = FakeCategoriaServiceNotFound([], total=0)

    with pytest.raises(HTTPException) as exc_info:
        await categorias_router.list_obras_by_categoria(
            categoria_id=categoria_id,
            user=user,
            pagination=PaginationParams(page=1, limit=50),
            svc=svc,
            search="Azul",
        )

    assert exc_info.value.status_code == 404
    assert svc.list_calls == []
