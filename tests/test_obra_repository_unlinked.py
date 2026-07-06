from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

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
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_list_unlinked_filters_by_team_and_null_orcamento():
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)
    team_id = uuid4()

    await repo.list_unlinked(team_id, page=1, limit=20, search=None)

    sql = _compiled_where(session.last_statement)
    assert f"obras.team_id = '{team_id}'" in sql
    assert "obras.arcaika_orcamento_id IS NULL" in sql
    assert "obras.is_deleted = false" in sql.lower()


@pytest.mark.asyncio
async def test_list_unlinked_applies_ilike_filter_when_search_given():
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)

    await repo.list_unlinked(uuid4(), page=1, limit=20, search="Aurora")

    sql = _compiled_where(session.last_statement)
    assert "obras.title ILIKE '%%Aurora%%'" in sql


@pytest.mark.asyncio
async def test_list_unlinked_omits_filter_when_search_is_blank():
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)

    await repo.list_unlinked(uuid4(), page=1, limit=20, search="   ")

    sql = _compiled_where(session.last_statement)
    assert "ilike" not in sql.lower()


@pytest.mark.asyncio
async def test_list_unlinked_paginates():
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)

    await repo.list_unlinked(uuid4(), page=2, limit=10, search=None)

    sql = str(session.last_statement)
    assert "LIMIT" in sql and "OFFSET" in sql


@pytest.mark.asyncio
async def test_count_unlinked_filters_by_team_and_null_orcamento():
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)
    team_id = uuid4()

    await repo.count_unlinked(team_id, search=None)

    sql = _compiled_where(session.last_statement)
    assert f"obras.team_id = '{team_id}'" in sql
    assert "obras.arcaika_orcamento_id IS NULL" in sql


@pytest.mark.asyncio
async def test_count_unlinked_applies_ilike_filter_when_search_given():
    session = _RecordingSession()
    repo = ObraRepositoryImpl(session)

    await repo.count_unlinked(uuid4(), search="Aurora")

    sql = _compiled_where(session.last_statement)
    assert "obras.title ILIKE '%%Aurora%%'" in sql
