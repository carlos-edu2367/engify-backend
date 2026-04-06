from redis.asyncio import Redis, from_url
from app.core.config import settings

# Singleton — criado na inicialização da app (lifespan)
_redis: Redis | None = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis não foi inicializado. Verifique o lifespan da aplicação.")
    return _redis


async def init_redis() -> None:
    global _redis
    _redis = from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
