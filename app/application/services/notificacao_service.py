from uuid import UUID
from app.domain.entities.notificacao import Notificacao, TipoNotificacao
from app.application.providers.repo.notificacao_repo import NotificacaoRepository
from app.application.dtos.notificacao import CreateNotificacaoDTO
from app.application.providers.uow import UOWProvider


class NotificacaoService:
    def __init__(self, notif_repo: NotificacaoRepository, uow: UOWProvider):
        self.notif_repo = notif_repo
        self.uow = uow

    async def list_notificacoes(self, user_id: UUID, team_id: UUID,
                                page: int, limit: int) -> list[Notificacao]:
        return await self.notif_repo.list_by_user(user_id, team_id, page, limit)

    async def count_notificacoes(self, user_id: UUID, team_id: UUID) -> int:
        return await self.notif_repo.count_by_user(user_id, team_id)

    async def count_nao_lidas(self, user_id: UUID, team_id: UUID) -> int:
        return await self.notif_repo.count_nao_lidas(user_id, team_id)

    async def marcar_lida(self, notif_id: UUID, user_id: UUID, team_id: UUID) -> Notificacao:
        notif = await self.notif_repo.get_by_id(notif_id, user_id)
        notif.marcar_lida()
        saved = await self.notif_repo.save(notif)
        await self.uow.commit()
        return saved

    async def marcar_todas_lidas(self, user_id: UUID, team_id: UUID) -> None:
        await self.notif_repo.marcar_todas_lidas(user_id, team_id)
        await self.uow.commit()
