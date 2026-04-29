import asyncio
from datetime import datetime, timezone

import structlog

from app.application.services.rh_solicitacoes_service import RhSolicitacoesService
from app.infra.db.repositories.rh_repository import (
    AjustePontoRepositoryImpl,
    AtestadoRepositoryImpl,
    FeriasRepositoryImpl,
    FuncionarioRepositoryImpl,
    RegistroPontoRepositoryImpl,
    RhAuditLogRepositoryImpl,
    TipoAtestadoRepositoryImpl,
)
from app.infra.db.session import async_session_factory
from app.infra.db.uow import SQLAlchemyUOW

logger = structlog.get_logger()

_CHECK_INTERVAL_SECONDS = 3600


async def expire_rh_atestados_once() -> int:
    async with async_session_factory() as session:
        service = RhSolicitacoesService(
            funcionario_repo=FuncionarioRepositoryImpl(session),
            ferias_repo=FeriasRepositoryImpl(session),
            ajuste_repo=AjustePontoRepositoryImpl(session),
            registro_ponto_repo=RegistroPontoRepositoryImpl(session),
            tipo_atestado_repo=TipoAtestadoRepositoryImpl(session),
            atestado_repo=AtestadoRepositoryImpl(session),
            audit_repo=RhAuditLogRepositoryImpl(session),
            uow=SQLAlchemyUOW(session),
        )
        expired = await service.expire_overdue_atestados(datetime.now(timezone.utc))
        logger.info("rh_atestado_expiration.completed", expired=expired)
        return expired


async def rh_atestado_expiration_loop() -> None:
    logger.info("rh_atestado_expiration.started")
    while True:
        try:
            await expire_rh_atestados_once()
        except Exception:
            logger.exception("rh_atestado_expiration.failed")
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
