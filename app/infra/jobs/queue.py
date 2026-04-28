from uuid import UUID

from app.application.providers.utility.report_queue import CommissionReportQueue
from app.core.config import settings


class ArqCommissionReportQueue(CommissionReportQueue):
    async def enqueue_generate_commission_report(self, job_id: UUID) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await redis.enqueue_job("generate_commission_report_job", str(job_id))
        finally:
            await redis.aclose()
