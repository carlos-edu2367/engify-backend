"""Job ARQ: entrega periódica dos webhooks de outbox ao Arcaika."""
import logging

from app.application.services.webhook_dispatcher import WebhookDispatcher
from app.infra.db.repositories.integracao_repository import (
    IntegrationEventRepositoryImpl, ArcaikaConnectionRepositoryImpl,
)
from app.infra.db.session import async_session_factory
from app.infra.db.uow import SQLAlchemyUOW
from app.infra.integracao.httpx_webhook_sender import HttpxWebhookSender

logger = logging.getLogger(__name__)


async def dispatch_integration_events_job(ctx) -> int:
    """Poll do outbox: entrega eventos prontos. Roda via cron do worker.

    A sessão do worker não tem `app.current_tenant` setado, então a policy RLS
    (branch `IS NULL`) permite ler eventos de todos os times — contexto de
    sistema confiável.
    """
    async with async_session_factory() as session:
        dispatcher = WebhookDispatcher(
            event_repo=IntegrationEventRepositoryImpl(session),
            connection_repo=ArcaikaConnectionRepositoryImpl(session),
            uow=SQLAlchemyUOW(session),
            sender=HttpxWebhookSender(),
        )
        delivered = await dispatcher.dispatch_due(limit=100)
        if delivered:
            logger.info("integracao_webhooks_entregues", extra={"delivered": delivered})
        return delivered
