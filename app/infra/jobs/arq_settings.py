from arq.connections import RedisSettings

from app.core.config import settings
from app.infra.jobs.handlers.commission_report_jobs import generate_commission_report_job
from app.infra.jobs.handlers.rh_jobs import expire_rh_atestados_job


class WorkerSettings:
    functions = [generate_commission_report_job, expire_rh_atestados_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 3
    job_timeout = 300
