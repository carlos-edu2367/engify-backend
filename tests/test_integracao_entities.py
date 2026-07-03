from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.domain.errors import DomainError
from app.domain.entities.integracao import (
    ArcaikaConnection, ConnectionScope, ConnectionStatus,
    IntegrationEvent, IntegrationEventType, EventStatus, RETRY_BACKOFF_SECONDS,
)


def _connection(**over):
    kwargs = dict(
        team_id=uuid4(),
        arcaika_organizacao_id=uuid4(),
        scopes=[ConnectionScope.OBRAS_WRITE],
        default_responsavel_id=uuid4(),
        webhook_secret="whsec",
    )
    kwargs.update(over)
    return ArcaikaConnection(**kwargs)


def test_connection_requires_responsavel():
    with pytest.raises(DomainError):
        _connection(default_responsavel_id=None)


def test_connection_scope_and_revoke():
    c = _connection(scopes=[ConnectionScope.OBRAS_WRITE, ConnectionScope.WEBHOOKS_MANAGE])
    assert c.has_scope(ConnectionScope.OBRAS_WRITE) is True
    assert c.has_scope(ConnectionScope.OBRAS_READ) is False
    c.revoke()
    assert c.status == ConnectionStatus.REVOKED
    assert c.refresh_token_hash is None
    assert c.has_scope(ConnectionScope.OBRAS_WRITE) is False  # revogada não tem escopo
    with pytest.raises(DomainError):
        c.ensure_active()


def test_set_webhook_url_requires_https():
    c = _connection()
    with pytest.raises(DomainError):
        c.set_webhook_url("http://inseguro.com/hook")
    c.set_webhook_url("https://arcaika.com/webhooks/engify")
    assert c.webhook_url == "https://arcaika.com/webhooks/engify"


def _event():
    return IntegrationEvent(
        team_id=uuid4(), obra_id=uuid4(),
        event_type=IntegrationEventType.OBRA_STATUS_CHANGED, payload={},
    )


def test_event_backoff_schedule_then_dead():
    e = _event()
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    # Falha repetidamente; cada falha agenda a próxima tentativa até esgotar.
    for i in range(1, e.max_attempts):
        e.mark_failed("boom", now)
        assert e.status == EventStatus.FAILED
        assert e.attempts == i
    # Última falha → DEAD
    e.mark_failed("boom", now)
    assert e.status == EventStatus.DEAD
    assert e.attempts == e.max_attempts == len(RETRY_BACKOFF_SECONDS)
    assert e.next_retry_at is None


def test_event_delivered_and_due():
    e = _event()
    assert e.is_due() is True  # pendente e sem next_retry no futuro
    e.mark_delivered()
    assert e.status == EventStatus.DELIVERED
    assert e.is_due() is False
