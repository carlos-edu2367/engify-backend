from datetime import datetime, timezone

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
