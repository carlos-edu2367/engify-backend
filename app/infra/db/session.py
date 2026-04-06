from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_recycle=settings.db_pool_recycle,
    # Echo apenas em dev para não logar queries em prod
    echo=settings.debug and settings.environment == "dev",
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Evita lazy loads após commit
    autoflush=False,         # Controle explícito de flush nos repositórios
    autocommit=False,
)


async def dispose_engine() -> None:
    """Chamado no shutdown para fechar todas as conexões."""
    await engine.dispose()
