"""
Entrega dos eventos de outbox como webhooks assinados ao Arcaika, com retry.

O worker chama `dispatch_due` periodicamente. Cada evento é assinado com o
segredo da conexão e entregue; falhas reagendam via backoff (ou vão p/ DLQ).
"""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.application.providers.repo.integracao_repo import (
    IntegrationEventRepository, ArcaikaConnectionRepository,
)
from app.application.providers.uow import UOWProvider
from app.application.services.integracao_payload import build_envelope
from app.infra.security.webhook_signing import build_headers

logger = logging.getLogger(__name__)


class WebhookSender(ABC):
    @abstractmethod
    async def post(self, url: str, body: str, headers: dict) -> int:
        """Envia o POST e retorna o status HTTP. Levanta em erro de transporte."""
        ...


class WebhookDispatcher:
    def __init__(
        self,
        event_repo: IntegrationEventRepository,
        connection_repo: ArcaikaConnectionRepository,
        uow: UOWProvider,
        sender: WebhookSender,
    ):
        self.event_repo = event_repo
        self.connection_repo = connection_repo
        self.uow = uow
        self.sender = sender

    async def dispatch_due(self, limit: int = 50) -> int:
        """Processa eventos prontos. Retorna quantos foram entregues com sucesso."""
        now = datetime.now(timezone.utc)
        events = await self.event_repo.list_due(limit, now)
        delivered = 0
        for event in events:
            connection = await self.connection_repo.get_by_team(event.team_id)
            if connection is None or not connection.is_active or not connection.webhook_url:
                event.mark_failed("conexão inativa ou sem webhook_url", now)
                await self.event_repo.save(event)
                await self.uow.commit()
                continue

            envelope = build_envelope(event, connection)
            body = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False, default=str)
            timestamp = str(int(now.timestamp()))
            headers = build_headers(connection.webhook_secret, timestamp, body, str(event.id))

            try:
                status = await self.sender.post(connection.webhook_url, body, headers)
                if 200 <= status < 300:
                    event.mark_delivered()
                    delivered += 1
                else:
                    event.mark_failed(f"HTTP {status}", now)
            except Exception as exc:  # transporte/timeout
                event.mark_failed(f"erro de transporte: {exc}", now)

            await self.event_repo.save(event)
            await self.uow.commit()
        return delivered
