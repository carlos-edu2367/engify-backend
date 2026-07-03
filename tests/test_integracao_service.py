from uuid import uuid4

import pytest

from app.application.services.integracao_service import IntegracaoArcaikaService
from app.http.schemas.integracao import CreateObraFromOrcamentoRequest, ExternalRef
from app.domain.entities.obra import Obra, ObraOrigem
from app.domain.entities.integracao import (
    ArcaikaConnection, ConnectionScope, IntegrationEventType,
)
from app.domain.errors import DomainError


class _FakeObraRepo:
    def __init__(self, existing=None):
        self._existing = existing
        self.saved = None

    async def get_by_arcaika_orcamento(self, orcamento_id):
        return self._existing

    async def get_by_id(self, obra_id, team_id=None):
        if self.saved and self.saved.id == obra_id:
            return self.saved
        raise DomainError("Obra não encontrada")

    async def save(self, obra):
        if obra.id is None:
            obra.id = uuid4()
        self.saved = obra
        return obra


class _FakeConnRepo:
    async def save(self, c):
        return c


class _FakeEventRepo:
    def __init__(self):
        self.events = []

    async def save(self, e):
        self.events.append(e)
        return e

    async def list_due(self, limit, now=None):
        return []


class _FakeUow:
    def __init__(self):
        self.committed = 0

    async def commit(self):
        self.committed += 1


def _svc(obra_repo, event_repo):
    return IntegracaoArcaikaService(
        obra_repo=obra_repo,
        connection_repo=_FakeConnRepo(),
        event_repo=event_repo,
        uow=_FakeUow(),
        public_url_for=lambda oid: f"https://engify/obras/{oid}/cliente",
    )


def _conn(scopes=None, default_resp=None):
    return ArcaikaConnection(
        team_id=uuid4(),
        arcaika_organizacao_id=uuid4(),
        scopes=scopes or [ConnectionScope.OBRAS_WRITE],
        default_responsavel_id=default_resp or uuid4(),
        webhook_secret="whsec",
    )


def _req(responsavel_id=None):
    return CreateObraFromOrcamentoRequest(
        external_ref=ExternalRef(
            orcamento_id=uuid4(), solicitacao_id=uuid4(), organizacao_id=uuid4()
        ),
        title="Pintura apto 302",
        description="Escopo do orçamento aprovado",
        valor=8500,
        responsavel_id=responsavel_id,
    )


@pytest.mark.asyncio
async def test_create_obra_new_emits_created_event_and_uses_default_responsavel():
    default_resp = uuid4()
    conn = _conn(default_resp=default_resp)
    obra_repo, event_repo = _FakeObraRepo(existing=None), _FakeEventRepo()
    svc = _svc(obra_repo, event_repo)

    obra, existed = await svc.create_obra_from_orcamento(conn, _req())

    assert existed is False
    assert obra.origem == ObraOrigem.ARCAIKA
    assert obra.responsavel_id == default_resp  # usou o default da conexão
    assert obra.team_id == conn.team_id
    assert len(event_repo.events) == 1
    assert event_repo.events[0].event_type == IntegrationEventType.OBRA_CREATED


@pytest.mark.asyncio
async def test_create_obra_idempotent_when_already_exists():
    existing = Obra(title="x", team_id=uuid4(), responsavel_id=uuid4(), description="", id=uuid4())
    obra_repo, event_repo = _FakeObraRepo(existing=existing), _FakeEventRepo()
    svc = _svc(obra_repo, event_repo)

    obra, existed = await svc.create_obra_from_orcamento(_conn(), _req())

    assert existed is True
    assert obra is existing
    assert event_repo.events == []  # não emite evento duplicado


@pytest.mark.asyncio
async def test_create_obra_requires_write_scope():
    conn = _conn(scopes=[ConnectionScope.OBRAS_READ])
    svc = _svc(_FakeObraRepo(existing=None), _FakeEventRepo())
    with pytest.raises(DomainError):
        await svc.create_obra_from_orcamento(conn, _req())


@pytest.mark.asyncio
async def test_explicit_responsavel_overrides_default():
    explicit = uuid4()
    conn = _conn(default_resp=uuid4())
    svc = _svc(_FakeObraRepo(existing=None), _FakeEventRepo())
    obra, _ = await svc.create_obra_from_orcamento(conn, _req(responsavel_id=explicit))
    assert obra.responsavel_id == explicit
