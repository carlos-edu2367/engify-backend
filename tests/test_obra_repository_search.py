from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.domain.entities.obra import Status
from app.infra.db.repositories.obra_repository import ObraRepositoryImpl


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)

    def scalar_one(self):
        return len(self._items)


class _RecordingSession:
    """Captura o último statement executado para inspecionar o SQL compilado."""

    def __init__(self):
        self.last_statement = None

    async def execute(self, stmt):
        self.last_statement = stmt
        return _FakeResult([])


def _compiled_where(stmt) -> str:
    # Compila contra o dialeto postgres (o usado em produção, ver app/core/config.py)
    # para que .ilike() renderize como ILIKE literal em vez do fallback genérico
    # lower(...) LIKE lower(...).
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _call_get_by_team(repo, team_id, search):
    return repo.get_by_team(team_id, page=1, limit=50, search=search)


def _call_count_by_team(repo, team_id, search):
    return repo.count_by_team(team_id, search=search)


def _call_get_by_status(repo, team_id, search):
    return repo.get_by_status(team_id, Status.EM_ANDAMENTO, limit=50, page=1, search=search)


def _call_count_by_status(repo, team_id, search):
    return repo.count_by_status(team_id, Status.EM_ANDAMENTO, search=search)


def _call_get_by_categoria(repo, team_id, search):
    return repo.get_by_categoria(uuid4(), team_id, page=1, limit=50, search=search)


def _call_count_by_categoria(repo, team_id, search):
    return repo.count_by_categoria(uuid4(), team_id, search=search)


METHOD_CALLERS = [
    pytest.param(_call_get_by_team, id="get_by_team"),
    pytest.param(_call_count_by_team, id="count_by_team"),
    pytest.param(_call_get_by_status, id="get_by_status"),
    pytest.param(_call_count_by_status, id="count_by_status"),
    pytest.param(_call_get_by_categoria, id="get_by_categoria"),
    pytest.param(_call_count_by_categoria, id="count_by_categoria"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("call_method", METHOD_CALLERS)
async def test_applies_ilike_filter_when_search_given(call_method):
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)
    team_id = uuid4()

    await call_method(repo, team_id, "Casa")

    sql = _compiled_where(session.last_statement)
    assert "obras.title ILIKE '%%Casa%%'" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("call_method", METHOD_CALLERS)
async def test_omits_filter_when_search_is_none(call_method):
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)
    team_id = uuid4()

    await call_method(repo, team_id, None)

    sql = _compiled_where(session.last_statement)
    assert "ilike" not in sql.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("call_method", METHOD_CALLERS)
async def test_omits_filter_when_search_is_blank(call_method):
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)
    team_id = uuid4()

    await call_method(repo, team_id, "   ")

    sql = _compiled_where(session.last_statement)
    assert "ilike" not in sql.lower()
