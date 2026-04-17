"""
Background task que roda de hora em hora verificando obras com prazo próximo.
Cria notificações para o responsável em T-7 dias e T-1 dia.
Usa ON CONFLICT DO NOTHING para que seja idempotente a cada ciclo.
"""
import asyncio
import structlog
from uuid import uuid4

from app.domain.entities.notificacao import Notificacao, TipoNotificacao
from app.infra.db.session import async_session_factory
from app.infra.db.repositories.notificacao_repository import NotificacaoRepositoryImpl
from app.infra.db.uow import SQLAlchemyUOW

logger = structlog.get_logger()

_CHECK_INTERVAL_SECONDS = 3600  # 1 hora


async def _check_prazo(dias: int, tipo: TipoNotificacao) -> None:
    label = "7 dias" if dias == 7 else "1 dia"
    async with async_session_factory() as session:
        try:
            repo = NotificacaoRepositoryImpl(session)
            uow = SQLAlchemyUOW(session)
            obras = await repo.list_obras_com_prazo(dias)
            for obra in obras:
                notif = Notificacao(
                    id=uuid4(),
                    user_id=obra["user_id"],
                    team_id=obra["team_id"],
                    tipo=tipo,
                    titulo=f"Prazo encerrando em {label}",
                    mensagem=f"A obra \"{obra['obra_title']}\" tem prazo de entrega em {label}.",
                    reference_id=obra["obra_id"],
                )
                await repo.save_ignore_conflict(notif)
            await uow.commit()
            if obras:
                logger.info("deadline_checker: notificacoes criadas",
                            dias=dias, quantidade=len(obras))
        except Exception:
            logger.exception("deadline_checker: erro ao verificar prazos", dias=dias)
            await session.rollback()


async def deadline_checker_loop() -> None:
    logger.info("deadline_checker: iniciado")
    while True:
        try:
            await _check_prazo(7, TipoNotificacao.PRAZO_7_DIAS)
            await _check_prazo(1, TipoNotificacao.PRAZO_1_DIA)
        except Exception:
            logger.exception("deadline_checker: erro inesperado no loop")
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
