from datetime import datetime, timezone
from uuid import UUID

from app.application.services.rh_solicitacoes_service import RhSolicitacoesService
from app.application.services.rh_folha_service import RhFolhaService
from app.infra.cache.rh_encargo_cache import NullRhEncargoCache
from app.infra.db.repositories.rh_repository import (
    AjustePontoRepositoryImpl,
    AtestadoRepositoryImpl,
    FeriasRepositoryImpl,
    FuncionarioRepositoryImpl,
    HoleriteItemRepositoryImpl,
    HoleriteRepositoryImpl,
    HorarioTrabalhoRepositoryImpl,
    RegraEncargoRepositoryImpl,
    RegistroPontoRepositoryImpl,
    RhAuditLogRepositoryImpl,
    RhFolhaJobRepositoryImpl,
    RhIdempotencyKeyRepositoryImpl,
    TipoAtestadoRepositoryImpl,
)
from app.infra.db.repositories.financeiro_repository import PagamentoAgendadoRepositoryImpl
from app.infra.db.session import async_session_factory
from app.infra.db.uow import SQLAlchemyUOW


async def expire_rh_atestados_job(ctx) -> int:
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
        return await service.expire_overdue_atestados(datetime.now(timezone.utc))


async def generate_rh_folha_job(ctx, job_id: str) -> dict:
    async with async_session_factory() as session:
        service = RhFolhaService(
            funcionario_repo=FuncionarioRepositoryImpl(session),
            horario_repo=HorarioTrabalhoRepositoryImpl(session),
            registro_ponto_repo=RegistroPontoRepositoryImpl(session),
            ferias_repo=FeriasRepositoryImpl(session),
            tipo_atestado_repo=TipoAtestadoRepositoryImpl(session),
            atestado_repo=AtestadoRepositoryImpl(session),
            holerite_repo=HoleriteRepositoryImpl(session),
            holerite_item_repo=HoleriteItemRepositoryImpl(session),
            regra_encargo_repo=RegraEncargoRepositoryImpl(session),
            pagamento_repo=PagamentoAgendadoRepositoryImpl(session),
            audit_repo=RhAuditLogRepositoryImpl(session),
            idempotency_repo=RhIdempotencyKeyRepositoryImpl(session),
            uow=SQLAlchemyUOW(session),
            folha_job_repo=RhFolhaJobRepositoryImpl(session),
            encargo_cache=NullRhEncargoCache(),
        )
        job = await service.processar_job_geracao_folha(UUID(job_id))
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "processados": job.processados,
            "falhas": job.falhas,
        }
