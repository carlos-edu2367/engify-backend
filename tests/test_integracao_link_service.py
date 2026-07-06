from uuid import uuid4

import pytest

from app.application.services.integracao_service import IntegracaoArcaikaService
from app.domain.entities.obra import Obra, ObraOrigem
from app.domain.entities.integracao import (
    ArcaikaConnection, ConnectionScope, IntegrationEventType,
)
from app.domain.errors import ConflictError, DomainError


class _FakeObraRepo:
    """Fake com um pequeno "banco" em memória, indexado por id."""

    def __init__(self, obras=None):
        self._by_id = {o.id: o for o in (obras or [])}

    async def get_by_id(self, obra_id, team_id=None):
        obra = self._by_id.get(obra_id)
        if obra is None or (team_id is not None and obra.team_id != team_id):
            raise DomainError("Obra não encontrada")
        return obra

    async def get_by_arcaika_orcamento(self, orcamento_id):
        for o in self._by_id.values():
            if o.arcaika_orcamento_id == orcamento_id:
                return o
        return None

    async def save(self, obra):
        if obra.id is None:
            obra.id = uuid4()
        self._by_id[obra.id] = obra
        return obra


class _FakeEventRepo:
    def __init__(self):
        self.events = []

    async def save(self, e):
        self.events.append(e)
        return e

    async def list_due(self, limit, now=None):
        return []


class _FakeConnRepo:
    async def save(self, c):
        return c


class _FakeUow:
    def __init__(self):
        self.committed = 0

    async def commit(self):
        self.committed += 1


def _svc(obra_repo, event_repo=None):
    return IntegracaoArcaikaService(
        obra_repo=obra_repo,
        connection_repo=_FakeConnRepo(),
        event_repo=event_repo or _FakeEventRepo(),
        uow=_FakeUow(),
        public_url_for=lambda oid: f"https://engify/obras/{oid}/cliente",
    )


def _conn(scopes=None):
    return ArcaikaConnection(
        team_id=uuid4(),
        arcaika_organizacao_id=uuid4(),
        scopes=scopes or [ConnectionScope.OBRAS_READ, ConnectionScope.OBRAS_WRITE],
        default_responsavel_id=uuid4(),
        webhook_secret="whsec",
    )


def _obra(team_id, arcaika_orcamento_id=None, arcaika_solicitacao_id=None):
    return Obra(
        title="Obra existente", team_id=team_id, responsavel_id=uuid4(),
        description="", id=uuid4(),
        arcaika_orcamento_id=arcaika_orcamento_id,
        arcaika_solicitacao_id=arcaika_solicitacao_id,
    )


# ── list_unlinked_obras ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_unlinked_obras_requires_read_scope():
    conn = _conn(scopes=[ConnectionScope.OBRAS_WRITE])
    svc = _svc(_FakeObraRepo())
    with pytest.raises(DomainError):
        await svc.list_unlinked_obras(conn, page=1, limit=20, search=None)


@pytest.mark.asyncio
async def test_list_unlinked_obras_returns_items_and_has_more(monkeypatch):
    conn = _conn()
    obra = _obra(conn.team_id)

    class _Repo(_FakeObraRepo):
        async def list_unlinked(self, team_id, page, limit, search=None):
            assert team_id == conn.team_id
            return [obra]

        async def count_unlinked(self, team_id, search=None):
            return 25

    svc = _svc(_Repo())
    itens, has_more = await svc.list_unlinked_obras(conn, page=1, limit=20, search=None)
    assert itens == [obra]
    assert has_more is True  # 1 * 20 < 25


@pytest.mark.asyncio
async def test_list_unlinked_obras_has_more_false_on_last_page():
    conn = _conn()

    class _Repo(_FakeObraRepo):
        async def list_unlinked(self, team_id, page, limit, search=None):
            return []

        async def count_unlinked(self, team_id, search=None):
            return 5

    svc = _svc(_Repo())
    _, has_more = await svc.list_unlinked_obras(conn, page=1, limit=20, search=None)
    assert has_more is False


# ── link_existing_obra ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_link_existing_grava_refs_e_emite_evento():
    conn = _conn()
    obra = _obra(conn.team_id)
    obra_repo = _FakeObraRepo([obra])
    event_repo = _FakeEventRepo()
    svc = _svc(obra_repo, event_repo)
    orc_id, sol_id = uuid4(), uuid4()

    saved, already = await svc.link_existing_obra(conn, obra.id, orc_id, sol_id)

    assert already is False
    assert saved.arcaika_orcamento_id == orc_id
    assert saved.arcaika_solicitacao_id == sol_id
    assert saved.origem == ObraOrigem.ARCAIKA
    assert len(event_repo.events) == 1
    assert event_repo.events[0].event_type == IntegrationEventType.OBRA_CREATED


@pytest.mark.asyncio
async def test_link_existing_idempotente_mesmo_par():
    conn = _conn()
    orc_id, sol_id = uuid4(), uuid4()
    obra = _obra(conn.team_id, arcaika_orcamento_id=orc_id, arcaika_solicitacao_id=sol_id)
    svc = _svc(_FakeObraRepo([obra]))

    saved, already = await svc.link_existing_obra(conn, obra.id, orc_id, sol_id)
    assert already is True
    assert saved.arcaika_orcamento_id == orc_id


@pytest.mark.asyncio
async def test_link_existing_obra_ja_vinculada_a_outro_orcamento_conflita():
    conn = _conn()
    obra = _obra(conn.team_id, arcaika_orcamento_id=uuid4())
    svc = _svc(_FakeObraRepo([obra]))

    with pytest.raises(ConflictError):
        await svc.link_existing_obra(conn, obra.id, uuid4(), uuid4())


@pytest.mark.asyncio
async def test_link_existing_orcamento_ja_em_outra_obra_conflita():
    conn = _conn()
    orc_id = uuid4()
    ja_vinculada = _obra(conn.team_id, arcaika_orcamento_id=orc_id)
    alvo = _obra(conn.team_id)
    svc = _svc(_FakeObraRepo([ja_vinculada, alvo]))

    with pytest.raises(ConflictError):
        await svc.link_existing_obra(conn, alvo.id, orc_id, uuid4())


@pytest.mark.asyncio
async def test_link_existing_obra_inexistente_ou_de_outro_team():
    conn = _conn()
    svc = _svc(_FakeObraRepo([]))
    with pytest.raises(DomainError):
        await svc.link_existing_obra(conn, uuid4(), uuid4(), uuid4())


@pytest.mark.asyncio
async def test_link_existing_requires_write_scope():
    conn = _conn(scopes=[ConnectionScope.OBRAS_READ])
    obra = _obra(conn.team_id)
    svc = _svc(_FakeObraRepo([obra]))
    with pytest.raises(DomainError):
        await svc.link_existing_obra(conn, obra.id, uuid4(), uuid4())
