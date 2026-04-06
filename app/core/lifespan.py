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

    yield

    logger.info("shutdown: liberando recursos")
    from app.http.dependencies.services import close_email_adapter
    await close_email_adapter()
    await close_redis()
    await dispose_engine()
    logger.info("shutdown: recursos liberados")
