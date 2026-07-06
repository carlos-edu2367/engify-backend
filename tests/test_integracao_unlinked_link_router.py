from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.http.routers import integracao as integracao_router
from app.http.schemas.integracao import ExternalRef, LinkObraRequest
from app.domain.entities.obra import Obra, ObraOrigem
from app.domain.entities.integracao import ArcaikaConnection, ConnectionScope
from app.domain.errors import ConflictError, DomainError


class FakeIntegracaoService:
    def __init__(self, itens=None, has_more=False, link_result=None, link_error=None):
        self.itens = itens or []
        self.has_more = has_more
        self.link_result = link_result
        self.link_error = link_error
        self.list_calls = []
        self.link_calls = []

    async def list_unlinked_obras(self, connection, page, limit, search=None):
        self.list_calls.append((connection, page, limit, search))
        return self.itens, self.has_more

    async def link_existing_obra(self, connection, obra_id, orcamento_id, solicitacao_id):
        self.link_calls.append((connection, obra_id, orcamento_id, solicitacao_id))
        if self.link_error is not None:
            raise self.link_error
        return self.link_result


def _conn():
    return ArcaikaConnection(
        team_id=uuid4(), arcaika_organizacao_id=uuid4(),
        scopes=[ConnectionScope.OBRAS_READ, ConnectionScope.OBRAS_WRITE],
        default_responsavel_id=uuid4(), webhook_secret="whsec",
    )


def _obra(team_id, valor=None):
    return Obra(
        title="Pintura Aurora", team_id=team_id, responsavel_id=uuid4(), description="",
        id=uuid4(), valor=valor, created_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_unlinked_obras_returns_items_and_page(monkeypatch):
    conn = _conn()
    obra = _obra(conn.team_id)
    svc = FakeIntegracaoService(itens=[obra], has_more=True)
    monkeypatch.setattr(integracao_router, "settings", SimpleNamespace(obra_public_url=lambda oid: f"https://x/obras/{oid}/cliente"))

    result = await integracao_router.list_unlinked_obras(
        connection=conn, svc=svc, q="aurora", page=1, limit=20,
    )

    assert svc.list_calls == [(conn, 1, 20, "aurora")]
    assert result.page == 1
    assert result.has_more is True
    assert result.items[0].obra_id == obra.id
    assert result.items[0].title == "Pintura Aurora"


@pytest.mark.asyncio
async def test_list_unlinked_obras_clamps_limit_to_100(monkeypatch):
    conn = _conn()
    svc = FakeIntegracaoService()
    monkeypatch.setattr(integracao_router, "settings", SimpleNamespace(obra_public_url=lambda oid: "url"))

    await integracao_router.list_unlinked_obras(connection=conn, svc=svc, q=None, page=1, limit=500)

    assert svc.list_calls[0][2] == 100


@pytest.mark.asyncio
async def test_list_unlinked_obras_403_when_domain_error(monkeypatch):
    conn = _conn()

    class _Svc(FakeIntegracaoService):
        async def list_unlinked_obras(self, connection, page, limit, search=None):
            raise DomainError("Conexão sem escopo obras:read")

    with pytest.raises(HTTPException) as ei:
        await integracao_router.list_unlinked_obras(connection=conn, svc=_Svc(), q=None, page=1, limit=20)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_link_existing_obra_200(monkeypatch):
    conn = _conn()
    obra = _obra(conn.team_id)
    svc = FakeIntegracaoService(link_result=(obra, False))
    monkeypatch.setattr(integracao_router, "settings", SimpleNamespace(obra_public_url=lambda oid: f"https://x/obras/{oid}/cliente"))
    orc_id, sol_id, org_id = uuid4(), uuid4(), uuid4()
    body = LinkObraRequest(external_ref=ExternalRef(orcamento_id=orc_id, solicitacao_id=sol_id, organizacao_id=org_id))

    result = await integracao_router.link_existing_obra(obra_id=obra.id, body=body, connection=conn, svc=svc)

    assert svc.link_calls == [(conn, obra.id, orc_id, sol_id)]
    assert result.obra_id == obra.id
    assert result.already_linked is False
    assert result.already_existed is True


@pytest.mark.asyncio
async def test_link_existing_obra_already_linked_true(monkeypatch):
    conn = _conn()
    obra = _obra(conn.team_id)
    svc = FakeIntegracaoService(link_result=(obra, True))
    monkeypatch.setattr(integracao_router, "settings", SimpleNamespace(obra_public_url=lambda oid: "url"))
    body = LinkObraRequest(external_ref=ExternalRef(
        orcamento_id=uuid4(), solicitacao_id=uuid4(), organizacao_id=uuid4()))

    result = await integracao_router.link_existing_obra(obra_id=obra.id, body=body, connection=conn, svc=svc)
    assert result.already_linked is True


@pytest.mark.asyncio
async def test_link_existing_obra_409_on_conflict():
    conn = _conn()
    svc = FakeIntegracaoService(link_error=ConflictError("Obra já vinculada a outro orçamento"))
    body = LinkObraRequest(external_ref=ExternalRef(
        orcamento_id=uuid4(), solicitacao_id=uuid4(), organizacao_id=uuid4()))

    with pytest.raises(HTTPException) as ei:
        await integracao_router.link_existing_obra(obra_id=uuid4(), body=body, connection=conn, svc=svc)
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_link_existing_obra_404_when_not_found():
    conn = _conn()
    svc = FakeIntegracaoService(link_error=DomainError("Obra não encontrada"))
    body = LinkObraRequest(external_ref=ExternalRef(
        orcamento_id=uuid4(), solicitacao_id=uuid4(), organizacao_id=uuid4()))

    with pytest.raises(HTTPException) as ei:
        await integracao_router.link_existing_obra(obra_id=uuid4(), body=body, connection=conn, svc=svc)
    assert ei.value.status_code == 404
