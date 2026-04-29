import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infra.cache.client import init_redis, close_redis
from app.infra.db.session import dispose_engine
import app.infra.db.models  # noqa: F401 — garante registro de todos os models no mapper
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação: startup e shutdown."""
    logger.info("startup: inicializando recursos")

    await init_redis()
    logger.info("startup: redis conectado")

    from app.infra.scheduler.deadline_checker import deadline_checker_loop
    from app.infra.scheduler.rh_atestado_expiration import rh_atestado_expiration_loop
    deadline_task = asyncio.create_task(deadline_checker_loop())
    rh_atestado_task = asyncio.create_task(rh_atestado_expiration_loop())
    logger.info("startup: deadline_checker iniciado")
    logger.info("startup: rh_atestado_expiration iniciado")

    yield

    logger.info("shutdown: liberando recursos")
    deadline_task.cancel()
    rh_atestado_task.cancel()
    try:
        await deadline_task
    except asyncio.CancelledError:
        pass
    try:
        await rh_atestado_task
    except asyncio.CancelledError:
        pass

    from app.http.dependencies.services import close_email_adapter
    await close_email_adapter()
    await close_redis()
    await dispose_engine()
    logger.info("shutdown: recursos liberados")
