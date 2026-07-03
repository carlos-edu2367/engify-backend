from uuid import uuid4

import pytest

from app.application.services.webhook_dispatcher import WebhookDispatcher
from app.domain.entities.integracao import (
    ArcaikaConnection, ConnectionScope, IntegrationEvent, IntegrationEventType, EventStatus,
)


class _FakeEventRepo:
    def __init__(self, due):
        self._due = due
        self.saved = []

    async def list_due(self, limit, now=None):
        return self._due

    async def save(self, e):
        self.saved.append(e)
        return e


class _FakeConnRepo:
    def __init__(self, conn):
        self._conn = conn

    async def get_by_team(self, team_id):
        return self._conn


class _FakeUow:
    async def commit(self):
        pass


class _RecordingSender:
    def __init__(self, status=200, raise_exc=False):
        self.status = status
        self.raise_exc = raise_exc
        self.calls = []

    async def post(self, url, body, headers):
        self.calls.append((url, body, headers))
        if self.raise_exc:
            raise RuntimeError("timeout")
        return self.status


def _conn(webhook_url="https://arcaika/webhooks/engify"):
    c = ArcaikaConnection(
        team_id=uuid4(), arcaika_organizacao_id=uuid4(),
        scopes=[ConnectionScope.OBRAS_WRITE, ConnectionScope.WEBHOOKS_MANAGE],
        default_responsavel_id=uuid4(), webhook_secret="whsec",
    )
    c.webhook_url = webhook_url
    return c


def _event(team_id):
    return IntegrationEvent(
        team_id=team_id, obra_id=uuid4(),
        event_type=IntegrationEventType.OBRA_STATUS_CHANGED,
        payload={"status": "em_andamento"},
    )


@pytest.mark.asyncio
async def test_delivers_and_signs_on_2xx():
    conn = _conn()
    event = _event(conn.team_id)
    sender = _RecordingSender(status=200)
    d = WebhookDispatcher(_FakeEventRepo([event]), _FakeConnRepo(conn), _FakeUow(), sender)

    delivered = await d.dispatch_due()

    assert delivered == 1
    assert event.status == EventStatus.DELIVERED
    # assinou com os headers esperados
    _, _, headers = sender.calls[0]
    assert headers["X-Engify-Signature"].startswith("sha256=")
    assert headers["X-Engify-Event-Id"] == str(event.id)


@pytest.mark.asyncio
async def test_non_2xx_marks_failed_and_reschedules():
    conn = _conn()
    event = _event(conn.team_id)
    d = WebhookDispatcher(_FakeEventRepo([event]), _FakeConnRepo(conn), _FakeUow(), _RecordingSender(status=500))

    delivered = await d.dispatch_due()

    assert delivered == 0
    assert event.status == EventStatus.FAILED
    assert event.attempts == 1
    assert event.next_retry_at is not None


@pytest.mark.asyncio
async def test_transport_error_marks_failed():
    conn = _conn()
    event = _event(conn.team_id)
    d = WebhookDispatcher(_FakeEventRepo([event]), _FakeConnRepo(conn), _FakeUow(), _RecordingSender(raise_exc=True))

    await d.dispatch_due()
    assert event.status == EventStatus.FAILED
    assert "transporte" in (event.last_error or "")


@pytest.mark.asyncio
async def test_no_webhook_url_marks_failed():
    conn = _conn(webhook_url=None)
    event = _event(conn.team_id)
    sender = _RecordingSender()
    d = WebhookDispatcher(_FakeEventRepo([event]), _FakeConnRepo(conn), _FakeUow(), sender)

    await d.dispatch_due()
    assert event.status == EventStatus.FAILED
    assert sender.calls == []  # nem tentou enviar
