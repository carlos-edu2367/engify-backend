from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from app.application.dtos.rh import (
    AjustePontoFiltersDTO,
    AtestadoFiltersDTO,
    CreateAjustePontoDTO,
    CreateAtestadoDTO,
    CreateFeriasDTO,
    CreateTipoAtestadoDTO,
    FeriasFiltersDTO,
    UpdateTipoAtestadoDTO,
)
from app.application.providers.repo.rh_repo import (
    AjustePontoRepository,
    AtestadoRepository,
    FeriasRepository,
    FuncionarioRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
    TipoAtestadoRepository,
)
from app.application.providers.uow import UOWProvider
from app.domain.entities.rh import (
    AjustePonto,
    Atestado,
    Ferias,
    RegistroPonto,
    RhAuditLog,
    StatusFerias,
    StatusPonto,
    TipoAtestado,
    TipoPonto,
)
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


class RhSolicitacoesService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        ferias_repo: FeriasRepository,
        ajuste_repo: AjustePontoRepository,
        registro_ponto_repo: RegistroPontoRepository,
        tipo_atestado_repo: TipoAtestadoRepository,
        atestado_repo: AtestadoRepository,
        audit_repo: RhAuditLogRepository,
        uow: UOWProvider,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.ferias_repo = ferias_repo
        self.ajuste_repo = ajuste_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.tipo_atestado_repo = tipo_atestado_repo
        self.atestado_repo = atestado_repo
        self.audit_repo = audit_repo
        self.uow = uow

    async def request_ferias(self, dto: CreateFeriasDTO, current_user: User) -> Ferias:
        funcionario = await self._resolve_funcionario_for_request(dto.funcionario_id, current_user)
        if await self.ferias_repo.has_overlap(
            funcionario.team_id,
            funcionario.id,
            dto.data_inicio,
            dto.data_fim,
            {StatusFerias.APROVADO, StatusFerias.EM_ANDAMENTO},
        ):
            raise DomainError("Ja existe ferias aprovada ou em andamento neste periodo")
        ferias = Ferias(
            team_id=funcionario.team_id,
            funcionario_id=funcionario.id,
            data_inicio=self._as_utc(dto.data_inicio),
            data_fim=self._as_utc(dto.data_fim),
        )
        saved = await self.ferias_repo.save(ferias)
        await self._record_audit(current_user, "ferias", saved.id, "rh.ferias.requested", after=self._ferias_snapshot(saved))
        await self.uow.commit()
        return saved

    async def list_ferias(self, current_user: User, filters: FeriasFiltersDTO, page: int, limit: int):
        team_id = current_user.team.id
        funcionario_id = filters.funcionario_id
        if current_user.role == Roles.FUNCIONARIO:
            funcionario = await self._get_current_funcionario(current_user)
            funcionario_id = funcionario.id
        else:
            self._ensure_rh_admin(current_user)
            if funcionario_id:
                await self.funcionario_repo.get_by_id(funcionario_id, team_id)
        items = await self.ferias_repo.list_by_filters(
            team_id,
            page,
            limit,
            funcionario_id=funcionario_id,
            status=filters.status,
            start=filters.start,
            end=filters.end,
        )
        total = await self.ferias_repo.count_by_filters(
            team_id,
            funcionario_id=funcionario_id,
            status=filters.status,
            start=filters.start,
            end=filters.end,
        )
        return items, total

    async def approve_ferias(self, ferias_id: UUID, current_user: User) -> Ferias:
        self._ensure_rh_admin(current_user)
        ferias = await self.ferias_repo.get_by_id(ferias_id, current_user.team.id)
        if await self.ferias_repo.has_overlap(
            ferias.team_id,
            ferias.funcionario_id,
            ferias.data_inicio,
            ferias.data_fim,
            {StatusFerias.APROVADO, StatusFerias.EM_ANDAMENTO},
            exclude_id=ferias.id,
        ):
            raise DomainError("Ja existe ferias aprovada ou em andamento neste periodo")
        before = self._ferias_snapshot(ferias)
        ferias.aprovar()
        saved = await self.ferias_repo.save(ferias)
        await self._record_audit(current_user, "ferias", saved.id, "rh.ferias.approved", before=before, after=self._ferias_snapshot(saved))
        await self.uow.commit()
        return saved

    async def reject_ferias(self, ferias_id: UUID, motivo: str, current_user: User) -> Ferias:
        self._ensure_rh_admin(current_user)
        ferias = await self.ferias_repo.get_by_id(ferias_id, current_user.team.id)
        before = self._ferias_snapshot(ferias)
        ferias.rejeitar(motivo)
        saved = await self.ferias_repo.save(ferias)
        await self._record_audit(current_user, "ferias", saved.id, "rh.ferias.rejected", before=before, after=self._ferias_snapshot(saved), reason=motivo)
        await self.uow.commit()
        return saved

    async def cancel_ferias(self, ferias_id: UUID, motivo: str, current_user: User) -> Ferias:
        self._ensure_rh_admin(current_user)
        ferias = await self.ferias_repo.get_by_id(ferias_id, current_user.team.id)
        before = self._ferias_snapshot(ferias)
        ferias.cancelar(motivo)
        saved = await self.ferias_repo.save(ferias)
        await self._record_audit(current_user, "ferias", saved.id, "rh.ferias.cancelled", before=before, after=self._ferias_snapshot(saved), reason=motivo)
        await self.uow.commit()
        return saved

    async def request_ajuste(self, dto: CreateAjustePontoDTO, current_user: User) -> AjustePonto:
        funcionario = await self._resolve_funcionario_for_request(dto.funcionario_id, current_user)
        self._ensure_requested_times_match_reference_day(dto)
        if await self.ajuste_repo.has_pending_duplicate(
            funcionario.team_id,
            funcionario.id,
            dto.data_referencia,
            dto.hora_entrada_solicitada,
            dto.hora_saida_solicitada,
        ):
            raise DomainError("Ja existe ajuste pendente para este dia e horario")
        ajuste = AjustePonto(
            team_id=funcionario.team_id,
            funcionario_id=funcionario.id,
            data_referencia=self._as_utc(dto.data_referencia),
            justificativa=dto.justificativa,
            hora_entrada_solicitada=self._as_utc(dto.hora_entrada_solicitada) if dto.hora_entrada_solicitada else None,
            hora_saida_solicitada=self._as_utc(dto.hora_saida_solicitada) if dto.hora_saida_solicitada else None,
        )
        saved = await self.ajuste_repo.save(ajuste)
        await self._record_audit(current_user, "ajuste_ponto", saved.id, "rh.ajuste_ponto.requested", after=self._ajuste_snapshot(saved))
        await self.uow.commit()
        return saved

    async def list_ajustes(self, current_user: User, filters: AjustePontoFiltersDTO, page: int, limit: int):
        team_id = current_user.team.id
        funcionario_id = filters.funcionario_id
        if current_user.role == Roles.FUNCIONARIO:
            funcionario = await self._get_current_funcionario(current_user)
            funcionario_id = funcionario.id
        else:
            self._ensure_rh_admin(current_user)
            if funcionario_id:
                await self.funcionario_repo.get_by_id(funcionario_id, team_id)
        items = await self.ajuste_repo.list_by_filters(team_id, page, limit, funcionario_id=funcionario_id, status=filters.status, start=filters.start, end=filters.end)
        total = await self.ajuste_repo.count_by_filters(team_id, funcionario_id=funcionario_id, status=filters.status, start=filters.start, end=filters.end)
        return items, total

    async def approve_ajuste(self, ajuste_id: UUID, current_user: User) -> AjustePonto:
        self._ensure_rh_admin(current_user)
        ajuste = await self.ajuste_repo.get_by_id(ajuste_id, current_user.team.id)
        await self.funcionario_repo.get_by_id(ajuste.funcionario_id, current_user.team.id)
        before = self._ajuste_snapshot(ajuste)
        day_start = self._day_start(ajuste.data_referencia)
        day_end = self._day_end(ajuste.data_referencia)
        existing = await self.registro_ponto_repo.list_by_funcionario_day(
            ajuste.team_id,
            ajuste.funcionario_id,
            day_start,
            day_end,
        )
        coordinates = self._coordinates_from_existing(existing)
        for registro in existing:
            registro.marcar_ajustado()
            await self.registro_ponto_repo.save(registro)
        if ajuste.hora_entrada_solicitada is not None:
            await self.registro_ponto_repo.save(
                self._build_adjusted_registro(ajuste, TipoPonto.ENTRADA, ajuste.hora_entrada_solicitada, coordinates)
            )
        if ajuste.hora_saida_solicitada is not None:
            await self.registro_ponto_repo.save(
                self._build_adjusted_registro(ajuste, TipoPonto.SAIDA, ajuste.hora_saida_solicitada, coordinates)
            )
        ajuste.aprovar()
        saved = await self.ajuste_repo.save(ajuste)
        await self._record_audit(current_user, "ajuste_ponto", saved.id, "rh.ajuste_ponto.approved", before=before, after=self._ajuste_snapshot(saved))
        await self.uow.commit()
        return saved

    async def reject_ajuste(self, ajuste_id: UUID, motivo: str, current_user: User) -> AjustePonto:
        self._ensure_rh_admin(current_user)
        ajuste = await self.ajuste_repo.get_by_id(ajuste_id, current_user.team.id)
        before = self._ajuste_snapshot(ajuste)
        ajuste.rejeitar(motivo)
        saved = await self.ajuste_repo.save(ajuste)
        await self._record_audit(current_user, "ajuste_ponto", saved.id, "rh.ajuste_ponto.rejected", before=before, after=self._ajuste_snapshot(saved), reason=motivo)
        await self.uow.commit()
        return saved

    async def create_tipo_atestado(self, dto: CreateTipoAtestadoDTO, current_user: User) -> TipoAtestado:
        self._ensure_rh_admin(current_user)
        tipo = TipoAtestado(
            team_id=current_user.team.id,
            nome=dto.nome,
            prazo_entrega_dias=dto.prazo_entrega_dias,
            abona_falta=dto.abona_falta,
            descricao=dto.descricao,
        )
        saved = await self.tipo_atestado_repo.save(tipo)
        await self._record_audit(current_user, "tipo_atestado", saved.id, "rh.tipo_atestado.created", after=self._tipo_snapshot(saved))
        await self.uow.commit()
        return saved

    async def list_tipos_atestado(self, current_user: User, page: int, limit: int):
        self._ensure_authenticated_rh_or_employee(current_user)
        items = await self.tipo_atestado_repo.list_active(current_user.team.id, page, limit)
        total = await self.tipo_atestado_repo.count_active(current_user.team.id)
        return items, total

    async def update_tipo_atestado(self, tipo_id: UUID, dto: UpdateTipoAtestadoDTO, current_user: User) -> TipoAtestado:
        self._ensure_rh_admin(current_user)
        tipo = await self.tipo_atestado_repo.get_by_id(tipo_id, current_user.team.id)
        before = self._tipo_snapshot(tipo)
        updated = TipoAtestado(
            team_id=tipo.team_id,
            nome=dto.nome if dto.nome is not None else tipo.nome,
            prazo_entrega_dias=dto.prazo_entrega_dias if dto.prazo_entrega_dias is not None else tipo.prazo_entrega_dias,
            abona_falta=dto.abona_falta if dto.abona_falta is not None else tipo.abona_falta,
            descricao=dto.descricao if dto.descricao is not None else tipo.descricao,
            id=tipo.id,
        )
        saved = await self.tipo_atestado_repo.save(updated)
        await self._record_audit(current_user, "tipo_atestado", saved.id, "rh.tipo_atestado.updated", before=before, after=self._tipo_snapshot(saved))
        await self.uow.commit()
        return saved

    async def delete_tipo_atestado(self, tipo_id: UUID, current_user: User) -> None:
        self._ensure_rh_admin(current_user)
        tipo = await self.tipo_atestado_repo.get_by_id(tipo_id, current_user.team.id)
        before = self._tipo_snapshot(tipo)
        tipo.delete()
        await self.tipo_atestado_repo.save(tipo)
        await self._record_audit(current_user, "tipo_atestado", tipo.id, "rh.tipo_atestado.deleted", before=before)
        await self.uow.commit()

    async def create_atestado(self, dto: CreateAtestadoDTO, current_user: User) -> Atestado:
        funcionario = await self._resolve_funcionario_for_request(dto.funcionario_id, current_user)
        await self.tipo_atestado_repo.get_by_id(dto.tipo_atestado_id, funcionario.team_id)
        atestado = Atestado(
            team_id=funcionario.team_id,
            funcionario_id=funcionario.id,
            tipo_atestado_id=dto.tipo_atestado_id,
            data_inicio=self._as_utc(dto.data_inicio),
            data_fim=self._as_utc(dto.data_fim),
            file_path=dto.file_path,
        )
        saved = await self.atestado_repo.save(atestado)
        await self._record_audit(current_user, "atestado", saved.id, "rh.atestado.created", after=self._atestado_snapshot(saved))
        await self.uow.commit()
        return saved

    async def list_atestados(self, current_user: User, filters: AtestadoFiltersDTO, page: int, limit: int):
        team_id = current_user.team.id
        funcionario_id = filters.funcionario_id
        if current_user.role == Roles.FUNCIONARIO:
            funcionario = await self._get_current_funcionario(current_user)
            funcionario_id = funcionario.id
        else:
            self._ensure_rh_admin(current_user)
            if funcionario_id:
                await self.funcionario_repo.get_by_id(funcionario_id, team_id)
        items = await self.atestado_repo.list_by_filters(
            team_id,
            page,
            limit,
            funcionario_id=funcionario_id,
            tipo_atestado_id=filters.tipo_atestado_id,
            status=filters.status,
            start=filters.start,
            end=filters.end,
        )
        total = await self.atestado_repo.count_by_filters(
            team_id,
            funcionario_id=funcionario_id,
            tipo_atestado_id=filters.tipo_atestado_id,
            status=filters.status,
            start=filters.start,
            end=filters.end,
        )
        return items, total

    async def obter_atestado_para_download(self, atestado_id: UUID, current_user: User) -> Atestado:
        atestado = await self.atestado_repo.get_by_id(atestado_id, current_user.team.id)
        if current_user.role == Roles.FUNCIONARIO:
            funcionario = await self._get_current_funcionario(current_user)
            if atestado.funcionario_id != funcionario.id:
                raise DomainError("Atestado nao encontrado")
        else:
            self._ensure_rh_admin(current_user)
        if not atestado.file_path:
            raise DomainError("Atestado sem arquivo anexado")
        return atestado

    async def deliver_atestado(self, atestado_id: UUID, file_path: str | None, current_user: User) -> Atestado:
        self._ensure_rh_admin(current_user)
        atestado = await self.atestado_repo.get_by_id(atestado_id, current_user.team.id)
        before = self._atestado_snapshot(atestado)
        if file_path is not None:
            atestado.file_path = file_path
        atestado.entregar()
        saved = await self.atestado_repo.save(atestado)
        await self._record_audit(current_user, "atestado", saved.id, "rh.atestado.delivered", before=before, after=self._atestado_snapshot(saved))
        await self.uow.commit()
        return saved

    async def reject_atestado(self, atestado_id: UUID, motivo: str, current_user: User) -> Atestado:
        self._ensure_rh_admin(current_user)
        atestado = await self.atestado_repo.get_by_id(atestado_id, current_user.team.id)
        before = self._atestado_snapshot(atestado)
        atestado.rejeitar(motivo)
        saved = await self.atestado_repo.save(atestado)
        await self._record_audit(current_user, "atestado", saved.id, "rh.atestado.rejected", before=before, after=self._atestado_snapshot(saved), reason=motivo)
        await self.uow.commit()
        return saved

    async def expire_overdue_atestados(self, now: datetime | None = None, team_id: UUID | None = None, limit: int = 500) -> int:
        reference = now or datetime.now(timezone.utc)
        candidates = await self.atestado_repo.list_due_for_expiration(reference, limit=limit, team_id=team_id)
        expired = 0
        for atestado in candidates:
            tipo = await self.tipo_atestado_repo.get_by_id(atestado.tipo_atestado_id, atestado.team_id)
            if atestado.created_at + timedelta(days=tipo.prazo_entrega_dias) < reference:
                before = self._atestado_snapshot(atestado)
                atestado.vencer()
                saved = await self.atestado_repo.save(atestado)
                await self._record_system_audit(saved.team_id, "atestado", saved.id, "rh.atestado.expired", before=before, after=self._atestado_snapshot(saved))
                expired += 1
        if expired:
            await self.uow.commit()
        return expired

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    def _ensure_authenticated_rh_or_employee(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO, Roles.FUNCIONARIO}:
            raise DomainError("Acesso restrito ao RH")

    async def _resolve_funcionario_for_request(self, funcionario_id: UUID | None, current_user: User):
        if current_user.role == Roles.FUNCIONARIO:
            return await self._get_current_funcionario(current_user)
        self._ensure_rh_admin(current_user)
        if funcionario_id is None:
            raise DomainError("Funcionario e obrigatorio")
        return await self.funcionario_repo.get_by_id(funcionario_id, current_user.team.id)

    async def _get_current_funcionario(self, current_user: User):
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None or funcionario.is_deleted or not funcionario.is_active:
            raise DomainError("Funcionario vinculado nao encontrado")
        return funcionario

    def _ensure_requested_times_match_reference_day(self, dto: CreateAjustePontoDTO) -> None:
        reference_day = self._as_utc(dto.data_referencia).date()
        for value in [dto.hora_entrada_solicitada, dto.hora_saida_solicitada]:
            if value is not None and self._as_utc(value).date() != reference_day:
                raise DomainError("Horario solicitado deve estar na data de referencia")

    def _coordinates_from_existing(self, registros: list[RegistroPonto]) -> tuple[float, float]:
        if not registros:
            return 0.0, 0.0
        return registros[0].latitude, registros[0].longitude

    def _build_adjusted_registro(self, ajuste: AjustePonto, tipo: TipoPonto, timestamp: datetime, coordinates: tuple[float, float]) -> RegistroPonto:
        latitude, longitude = coordinates
        return RegistroPonto(
            team_id=ajuste.team_id,
            funcionario_id=ajuste.funcionario_id,
            tipo=tipo,
            timestamp=self._as_utc(timestamp),
            latitude=latitude,
            longitude=longitude,
            status=StatusPonto.AJUSTADO,
        )

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _day_start(self, value: datetime) -> datetime:
        return datetime.combine(self._as_utc(value).date(), time.min, tzinfo=timezone.utc)

    def _day_end(self, value: datetime) -> datetime:
        return datetime.combine(self._as_utc(value).date(), time.max, tzinfo=timezone.utc)

    async def _record_audit(self, current_user: User, entity_type: str, entity_id: UUID, action: str, before=None, after=None, reason: str | None = None) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
                reason=reason,
            )
        )

    async def _record_system_audit(self, team_id: UUID, entity_type: str, entity_id: UUID, action: str, before=None, after=None) -> None:
        await self.audit_repo.save(
            RhAuditLog(
                team_id=team_id,
                actor_user_id=None,
                actor_role="system",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before,
                after=after,
            )
        )

    def _ferias_snapshot(self, ferias: Ferias) -> dict:
        return {
            "funcionario_id": str(ferias.funcionario_id),
            "data_inicio": ferias.data_inicio.isoformat(),
            "data_fim": ferias.data_fim.isoformat(),
            "status": ferias.status.value,
        }

    def _ajuste_snapshot(self, ajuste: AjustePonto) -> dict:
        return {
            "funcionario_id": str(ajuste.funcionario_id),
            "data_referencia": ajuste.data_referencia.isoformat(),
            "status": ajuste.status.value,
            "hora_entrada_solicitada": ajuste.hora_entrada_solicitada.isoformat() if ajuste.hora_entrada_solicitada else None,
            "hora_saida_solicitada": ajuste.hora_saida_solicitada.isoformat() if ajuste.hora_saida_solicitada else None,
        }

    def _tipo_snapshot(self, tipo: TipoAtestado) -> dict:
        return {
            "nome": tipo.nome,
            "prazo_entrega_dias": tipo.prazo_entrega_dias,
            "abona_falta": tipo.abona_falta,
            "is_deleted": tipo.is_deleted,
        }

    def _atestado_snapshot(self, atestado: Atestado) -> dict:
        return {
            "funcionario_id": str(atestado.funcionario_id),
            "tipo_atestado_id": str(atestado.tipo_atestado_id),
            "data_inicio": atestado.data_inicio.isoformat(),
            "data_fim": atestado.data_fim.isoformat(),
            "status": atestado.status.value,
            "has_file": bool(atestado.file_path),
        }
