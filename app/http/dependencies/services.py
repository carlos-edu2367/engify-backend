"""
Factories de serviços usando FastAPI Depends.
Cada factory cria o serviço com as dependências concretas injetadas.
A session é criada por request e fechada ao final (via generator).
"""
import logging
from typing import Annotated, AsyncGenerator
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import async_session_factory
from app.infra.db.uow import SQLAlchemyUOW
from app.infra.db.repositories.user_repository import (
    UserRepositoryImpl, SolicitacaoRepoImpl, RecoveryRepoImpl
)
from app.infra.db.repositories.team_repository import TeamRepositoryImpl, DiaristRepositoryImpl
from app.infra.security.hash import Argon2HashProvider
from app.infra.storage.s3_provider import S3StorageProvider
from app.application.ports.email_port import EmailPort
from app.application.services.user_service import UserService, RecoveryPasswordService
from app.application.services.team_service import TeamService, DiaristService
from app.application.services.obra_service import (
    ObraService, ItemService, DiaryService,
    ItemAttachmentService, ObraImageService, MuralService, CategoriaObraService,
    RecebimentoService,
)
from app.application.services.notificacao_service import NotificacaoService
from app.application.services.financeiro_service import FinanceiroService
from app.application.services.rh_audit_service import RhAuditService
from app.application.services.rh_dashboard_service import RhDashboardService
from app.application.services.rh_funcionario_service import RhFuncionarioService
from app.application.services.rh_ponto_service import RhLocalPontoService, RhPontoService
from app.application.services.rh_folha_service import RhFolhaService
from app.application.services.rh_encargo_service import RhEncargoService
from app.application.services.rh_solicitacoes_service import RhSolicitacoesService
from app.infra.cache.rh_geofence_cache import RedisRhGeofenceCache
from app.infra.cache.rh_encargo_cache import NullRhEncargoCache
from app.infra.db.repositories.obra_repository import (
    ObraRepositoryImpl, ItemRepositoryImpl, DiaryRepositoryImpl,
    ItemAttachmentRepositoryImpl, ImageRepositoryImpl, CategoriaObraRepositoryImpl,
)
from app.infra.db.repositories.mural_repository import MuralRepositoryImpl
from app.infra.db.repositories.financeiro_repository import (
    MovimentacaoRepositoryImpl, PagamentoAgendadoRepositoryImpl,
    MovimentacaoAttachmentRepositoryImpl
)
from app.infra.db.repositories.rh_repository import (
    FuncionarioRepositoryImpl,
    RegraEncargoRepositoryImpl,
    HorarioTrabalhoRepositoryImpl,
    LocalPontoRepositoryImpl,
    RegistroPontoRepositoryImpl,
    RhAuditLogRepositoryImpl,
    RhIdempotencyKeyRepositoryImpl,
    AjustePontoRepositoryImpl,
    AtestadoRepositoryImpl,
    FeriasRepositoryImpl,
    HoleriteItemRepositoryImpl,
    TipoAtestadoRepositoryImpl,
    HoleriteRepositoryImpl,
    RhFolhaJobRepositoryImpl,
    RhSalarioHistoricoRepositoryImpl,
    TabelaProgressivaRepositoryImpl,
)
from app.infra.db.repositories.notificacao_repository import NotificacaoRepositoryImpl
from app.infra.db.repositories.report_job_repository import ReportJobRepositoryImpl
from app.application.use_cases.generate_monthly_commission_report import (
    GenerateMonthlyCommissionReportUseCase,
    GetCommissionReportJobStatusUseCase,
)
from app.infra.jobs.queue import ArqCommissionReportQueue
from app.infra.jobs.rh_queue import ArqRhFolhaQueue

logger = logging.getLogger(__name__)


def _criar_email_adapter() -> EmailPort | None:
    """Cria o adapter Mailgun se as variáveis de ambiente estiverem configuradas."""
    from app.core.config import settings
    if not settings.mailgun_api_key or not settings.mailgun_domain:
        logger.warning(
            "MAILGUN_API_KEY ou MAILGUN_DOMAIN não configurados. "
            "Emails não serão enviados."
        )
        return None
    from app.infra.email.mailgun_adapter import MailgunEmailAdapter
    return MailgunEmailAdapter(
        api_key=settings.mailgun_api_key,
        domain=settings.mailgun_domain,
        remetente=settings.mailgun_from,
        frontend_url=settings.frontend_url,
    )


_email_adapter: EmailPort | None = _criar_email_adapter()


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            # RLS — define o tenant da sessão para que as policies do PostgreSQL
            # sejam aplicadas como defesa em profundidade.
            # SET LOCAL é transaction-scoped; válido até o próximo COMMIT/ROLLBACK.
            team_id = getattr(request.state, "team_id", None)
            if team_id:
                await session.execute(
                    text("SELECT set_config('app.current_tenant', :tid, true)"),
                    {"tid": str(team_id)},
                )
            yield session
        except Exception:
            await session.rollback()
            raise


Session = Annotated[AsyncSession, Depends(get_session)]

_hash_provider = Argon2HashProvider()
_storage_provider = S3StorageProvider()
_report_queue = ArqCommissionReportQueue()
_rh_geofence_cache = RedisRhGeofenceCache()
_rh_folha_queue = ArqRhFolhaQueue()
_rh_encargo_cache = NullRhEncargoCache()


def get_hash_provider() -> Argon2HashProvider:
    return _hash_provider


def get_storage_provider() -> S3StorageProvider:
    return _storage_provider


async def close_email_adapter() -> None:
    """Chamado no shutdown para fechar o cliente HTTP do email adapter."""
    if _email_adapter:
        await _email_adapter.fechar()


async def get_user_service(session: Session) -> UserService:
    return UserService(
        user_repo=UserRepositoryImpl(session),
        hash=_hash_provider,
        uow=SQLAlchemyUOW(session),
        solicitacao_repo=SolicitacaoRepoImpl(session),
        team_repo=TeamRepositoryImpl(session),
        email_port=_email_adapter,
    )


async def get_recovery_service(session: Session) -> RecoveryPasswordService:
    return RecoveryPasswordService(
        user_repo=UserRepositoryImpl(session),
        recovery_repo=RecoveryRepoImpl(session),
        hash=_hash_provider,
        uow=SQLAlchemyUOW(session),
        email_port=_email_adapter,
    )


async def get_team_service(session: Session) -> TeamService:
    return TeamService(
        team_repo=TeamRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
        user_repo=UserRepositoryImpl(session),
        hash=_hash_provider,
    )


async def get_diarist_service(session: Session) -> DiaristService:
    return DiaristService(
        team_repo=TeamRepositoryImpl(session),
        diarist_repo=DiaristRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_obra_service(session: Session) -> ObraService:
    return ObraService(
        obra_repo=ObraRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_item_service(session: Session) -> ItemService:
    return ItemService(
        item_repo=ItemRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_diary_service(session: Session) -> DiaryService:
    return DiaryService(
        obra_repo=ObraRepositoryImpl(session),
        diarist_repo=DiaristRepositoryImpl(session),
        diary_repo=DiaryRepositoryImpl(session),
        pagamento_repo=PagamentoAgendadoRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_financeiro_service(session: Session) -> FinanceiroService:
    return FinanceiroService(
        mov_repo=MovimentacaoRepositoryImpl(session),
        pagamento_repo=PagamentoAgendadoRepositoryImpl(session),
        mov_attachment_repo=MovimentacaoAttachmentRepositoryImpl(session),
        diarist_repo=DiaristRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_rh_audit_service(session: Session) -> RhAuditService:
    return RhAuditService(
        audit_repo=RhAuditLogRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_rh_funcionario_service(session: Session) -> RhFuncionarioService:
    return RhFuncionarioService(
        funcionario_repo=FuncionarioRepositoryImpl(session),
        horario_repo=HorarioTrabalhoRepositoryImpl(session),
        user_repo=UserRepositoryImpl(session),
        audit_repo=RhAuditLogRepositoryImpl(session),
        salario_historico_repo=RhSalarioHistoricoRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_rh_local_ponto_service(session: Session) -> RhLocalPontoService:
    return RhLocalPontoService(
        funcionario_repo=FuncionarioRepositoryImpl(session),
        local_ponto_repo=LocalPontoRepositoryImpl(session),
        audit_repo=RhAuditLogRepositoryImpl(session),
        geofence_cache=_rh_geofence_cache,
        uow=SQLAlchemyUOW(session),
    )


async def get_rh_ponto_service(session: Session) -> RhPontoService:
    return RhPontoService(
        funcionario_repo=FuncionarioRepositoryImpl(session),
        local_ponto_repo=LocalPontoRepositoryImpl(session),
        registro_ponto_repo=RegistroPontoRepositoryImpl(session),
        audit_repo=RhAuditLogRepositoryImpl(session),
        geofence_cache=_rh_geofence_cache,
        idempotency_repo=RhIdempotencyKeyRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_rh_solicitacoes_service(session: Session) -> RhSolicitacoesService:
    return RhSolicitacoesService(
        funcionario_repo=FuncionarioRepositoryImpl(session),
        ferias_repo=FeriasRepositoryImpl(session),
        ajuste_repo=AjustePontoRepositoryImpl(session),
        registro_ponto_repo=RegistroPontoRepositoryImpl(session),
        tipo_atestado_repo=TipoAtestadoRepositoryImpl(session),
        atestado_repo=AtestadoRepositoryImpl(session),
        audit_repo=RhAuditLogRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_rh_folha_service(session: Session) -> RhFolhaService:
    return RhFolhaService(
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
        folha_queue=_rh_folha_queue,
        encargo_cache=_rh_encargo_cache,
    )


async def get_rh_encargo_service(session: Session) -> RhEncargoService:
    return RhEncargoService(
        regra_repo=RegraEncargoRepositoryImpl(session),
        tabela_repo=TabelaProgressivaRepositoryImpl(session),
        audit_repo=RhAuditLogRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
        encargo_cache=_rh_encargo_cache,
    )


async def get_rh_dashboard_service(session: Session) -> RhDashboardService:
    return RhDashboardService(
        funcionario_repo=FuncionarioRepositoryImpl(session),
        ajuste_repo=AjustePontoRepositoryImpl(session),
        ferias_repo=FeriasRepositoryImpl(session),
        atestado_repo=AtestadoRepositoryImpl(session),
        registro_ponto_repo=RegistroPontoRepositoryImpl(session),
        holerite_repo=HoleriteRepositoryImpl(session),
        audit_repo=RhAuditLogRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_item_attachment_service(session: Session) -> ItemAttachmentService:
    return ItemAttachmentService(
        attachment_repo=ItemAttachmentRepositoryImpl(session),
        item_repo=ItemRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_obra_image_service(session: Session) -> ObraImageService:
    return ObraImageService(
        image_repo=ImageRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_mural_service(session: Session) -> MuralService:
    return MuralService(
        mural_repo=MuralRepositoryImpl(session),
        obra_repo=ObraRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
        notif_repo=NotificacaoRepositoryImpl(session),
    )


async def get_notificacao_service(session: Session) -> NotificacaoService:
    return NotificacaoService(
        notif_repo=NotificacaoRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_categoria_obra_service(session: Session) -> CategoriaObraService:
    return CategoriaObraService(
        categoria_repo=CategoriaObraRepositoryImpl(session),
        obra_repo=ObraRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_recebimento_service(session: Session) -> RecebimentoService:
    return RecebimentoService(
        obra_repo=ObraRepositoryImpl(session),
        mov_repo=MovimentacaoRepositoryImpl(session),
        uow=SQLAlchemyUOW(session),
    )


async def get_generate_commission_report_use_case(
    session: Session,
) -> GenerateMonthlyCommissionReportUseCase:
    return GenerateMonthlyCommissionReportUseCase(
        report_job_repo=ReportJobRepositoryImpl(session),
        categoria_repo=CategoriaObraRepositoryImpl(session),
        job_queue=_report_queue,
        uow=SQLAlchemyUOW(session),
    )


async def get_commission_report_job_status_use_case(
    session: Session,
) -> GetCommissionReportJobStatusUseCase:
    from app.core.config import settings

    return GetCommissionReportJobStatusUseCase(
        report_job_repo=ReportJobRepositoryImpl(session),
        storage_provider=_storage_provider,
        bucket_name=settings.storage_bucket_name,
        download_expires_in=settings.storage_download_expires_in,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
RecoveryServiceDep = Annotated[RecoveryPasswordService, Depends(get_recovery_service)]
TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]
DiaristServiceDep = Annotated[DiaristService, Depends(get_diarist_service)]
ObraServiceDep = Annotated[ObraService, Depends(get_obra_service)]
ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
DiaryServiceDep = Annotated[DiaryService, Depends(get_diary_service)]
FinanceiroServiceDep = Annotated[FinanceiroService, Depends(get_financeiro_service)]
RhAuditServiceDep = Annotated[RhAuditService, Depends(get_rh_audit_service)]
RhFuncionarioServiceDep = Annotated[RhFuncionarioService, Depends(get_rh_funcionario_service)]
RhLocalPontoServiceDep = Annotated[RhLocalPontoService, Depends(get_rh_local_ponto_service)]
RhPontoServiceDep = Annotated[RhPontoService, Depends(get_rh_ponto_service)]
RhSolicitacoesServiceDep = Annotated[RhSolicitacoesService, Depends(get_rh_solicitacoes_service)]
RhFolhaServiceDep = Annotated[RhFolhaService, Depends(get_rh_folha_service)]
RhEncargoServiceDep = Annotated[RhEncargoService, Depends(get_rh_encargo_service)]
RhDashboardServiceDep = Annotated[RhDashboardService, Depends(get_rh_dashboard_service)]
ItemAttachmentServiceDep = Annotated[ItemAttachmentService, Depends(get_item_attachment_service)]
ObraImageServiceDep = Annotated[ObraImageService, Depends(get_obra_image_service)]
MuralServiceDep = Annotated[MuralService, Depends(get_mural_service)]
CategoriaObraServiceDep = Annotated[CategoriaObraService, Depends(get_categoria_obra_service)]
RecebimentoServiceDep = Annotated[RecebimentoService, Depends(get_recebimento_service)]
NotificacaoServiceDep = Annotated[NotificacaoService, Depends(get_notificacao_service)]
StorageProviderDep = Annotated[S3StorageProvider, Depends(get_storage_provider)]
GenerateCommissionReportUseCaseDep = Annotated[
    GenerateMonthlyCommissionReportUseCase, Depends(get_generate_commission_report_use_case)
]
CommissionReportJobStatusUseCaseDep = Annotated[
    GetCommissionReportJobStatusUseCase, Depends(get_commission_report_job_status_use_case)
]
