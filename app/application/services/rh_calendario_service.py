from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.dtos.rh import CreateEventoCalendarioDTO
from app.application.providers.repo.rh_repo import EventoCalendarioRepository, RhAuditLogRepository
from app.application.providers.uow import UOWProvider
from app.domain.entities.rh import RhAuditLog
from app.domain.entities.rh_calendario import EventoCalendarioRh, TipoEventoCalendario
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


class RhCalendarioService:
    def __init__(
        self,
        evento_repo: EventoCalendarioRepository,
        audit_repo: RhAuditLogRepository,
        uow: UOWProvider,
    ) -> None:
        self.evento_repo = evento_repo
        self.audit_repo = audit_repo
        self.uow = uow

    async def criar_evento(self, dto: CreateEventoCalendarioDTO, current_user: User) -> EventoCalendarioRh:
        self._ensure_rh_admin(current_user)
        evento = EventoCalendarioRh(
            team_id=current_user.team.id,
            tipo=TipoEventoCalendario(dto.tipo),
            data=dto.data,
            descricao=dto.descricao,
            hora_corte=dto.hora_corte,
            aplica_todos=dto.aplica_todos,
            funcionario_ids=dto.funcionario_ids,
        )
        saved = await self.evento_repo.save(evento)
        await self._record_audit(current_user, saved.id, "rh.calendario.evento_criado", after=self._snapshot(saved))
        await self.uow.commit()
        return saved

    async def list_eventos(self, current_user: User, start: date, end: date) -> list[EventoCalendarioRh]:
        self._ensure_rh_admin(current_user)
        return await self.evento_repo.list_by_periodo(current_user.team.id, start, end)

    async def remover_evento(self, evento_id: UUID, current_user: User) -> None:
        self._ensure_rh_admin(current_user)
        evento = await self.evento_repo.get_by_id(evento_id, current_user.team.id)
        before = self._snapshot(evento)
        evento.delete()
        await self.evento_repo.save(evento)
        await self._record_audit(current_user, evento.id, "rh.calendario.evento_removido", before=before)
        await self.uow.commit()

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _snapshot(self, evento: EventoCalendarioRh) -> dict:
        return {
            "tipo": evento.tipo.value,
            "data": evento.data.isoformat(),
            "descricao": evento.descricao,
            "hora_corte": evento.hora_corte.isoformat() if evento.hora_corte else None,
            "aplica_todos": evento.aplica_todos,
            "funcionario_ids": [str(item) for item in evento.funcionario_ids],
            "is_deleted": evento.is_deleted,
        }

    async def _record_audit(self, current_user: User, entity_id: UUID, action: str, before=None, after=None) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type="evento_calendario",
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
            )
        )
