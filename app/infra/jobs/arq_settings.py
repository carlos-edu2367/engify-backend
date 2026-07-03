from arq.connections import RedisSettings
from arq import cron

from app.core.config import settings
from app.infra.jobs.handlers.commission_report_jobs import generate_commission_report_job
from app.infra.jobs.handlers.rh_jobs import expire_rh_atestados_job, generate_rh_folha_job
from app.infra.jobs.handlers.integracao_jobs import dispatch_integration_events_job


class WorkerSettings:
    functions = [
        generate_commission_report_job,
        expire_rh_atestados_job,
        generate_rh_folha_job,
        dispatch_integration_events_job,
    ]
    # Poll do outbox de webhooks a cada 30s (segundos 0 e 30 de cada minuto).
    cron_jobs = [
        cron(dispatch_integration_events_job, second={0, 30}, run_at_startup=False),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 3
    job_timeout = 300
