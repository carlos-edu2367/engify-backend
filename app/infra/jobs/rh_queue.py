from uuid import UUID

from app.application.providers.utility.rh_folha_queue import RhFolhaQueuePort
from app.core.config import settings


class ArqRhFolhaQueue(RhFolhaQueuePort):
    async def enqueue_generate_folha(self, job_id: UUID) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await redis.enqueue_job("generate_rh_folha_job", str(job_id))
        finally:
            await redis.aclose()
