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
from app.application.services.financeiro_service import FinanceiroService
from app.infra.db.repositories.obra_repository import (
    ObraRepositoryImpl, ItemRepositoryImpl, DiaryRepositoryImpl,
    ItemAttachmentRepositoryImpl, ImageRepositoryImpl, CategoriaObraRepositoryImpl,
)
from app.infra.db.repositories.mural_repository import MuralRepositoryImpl
from app.infra.db.repositories.financeiro_repository import (
    MovimentacaoRepositoryImpl, PagamentoAgendadoRepositoryImpl,
    MovimentacaoAttachmentRepositoryImpl
)

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


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
RecoveryServiceDep = Annotated[RecoveryPasswordService, Depends(get_recovery_service)]
TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]
DiaristServiceDep = Annotated[DiaristService, Depends(get_diarist_service)]
ObraServiceDep = Annotated[ObraService, Depends(get_obra_service)]
ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
DiaryServiceDep = Annotated[DiaryService, Depends(get_diary_service)]
FinanceiroServiceDep = Annotated[FinanceiroService, Depends(get_financeiro_service)]
ItemAttachmentServiceDep = Annotated[ItemAttachmentService, Depends(get_item_attachment_service)]
ObraImageServiceDep = Annotated[ObraImageService, Depends(get_obra_image_service)]
MuralServiceDep = Annotated[MuralService, Depends(get_mural_service)]
CategoriaObraServiceDep = Annotated[CategoriaObraService, Depends(get_categoria_obra_service)]
RecebimentoServiceDep = Annotated[RecebimentoService, Depends(get_recebimento_service)]
StorageProviderDep = Annotated[S3StorageProvider, Depends(get_storage_provider)]
