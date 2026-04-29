from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from uuid import UUID

from pydantic import BaseModel

from app.application.dtos.rh import CreateLocalPontoDTO, RegistrarPontoDTO, UpdateLocalPontoDTO
from app.application.providers.repo.rh_repo import (
    FuncionarioRepository,
    LocalPontoRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
    RhIdempotencyKeyRepository,
)
from app.application.providers.uow import UOWProvider
from app.application.providers.utility.rh_geofence_cache import RhGeofenceCache
from app.domain.entities.rh import LocalPonto, RegistroPonto, RhAuditLog, StatusPonto, TipoPonto
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


EARTH_RADIUS_METERS = 6_371_000


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c


@dataclass
class RequestContext:
    request_id: str | None = None
    ip_hash: str | None = None
    user_agent: str | None = None
    idempotency_key: str | None = None


class RhLocalPontoService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        local_ponto_repo: LocalPontoRepository,
        audit_repo: RhAuditLogRepository,
        geofence_cache: RhGeofenceCache,
        uow: UOWProvider,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.local_ponto_repo = local_ponto_repo
        self.audit_repo = audit_repo
        self.geofence_cache = geofence_cache
        self.uow = uow

    async def list_locais(self, funcionario_id: UUID, current_user: User, page: int, limit: int):
        self._ensure_rh_admin(current_user)
        await self.funcionario_repo.get_by_id(funcionario_id, current_user.team.id)
        items = await self.local_ponto_repo.list_by_funcionario(current_user.team.id, funcionario_id)
        total = len(items)
        return items[(page - 1) * limit : page * limit], total

    async def create_local(self, funcionario_id: UUID, dto: CreateLocalPontoDTO, current_user: User) -> LocalPonto:
        self._ensure_rh_admin(current_user)
        funcionario = await self.funcionario_repo.get_by_id(funcionario_id, current_user.team.id)
        local = LocalPonto(
            team_id=current_user.team.id,
            funcionario_id=funcionario.id,
            nome=dto.nome,
            latitude=dto.latitude,
            longitude=dto.longitude,
            raio_metros=dto.raio_metros,
        )
        saved = await self.local_ponto_repo.save(local)
        await self._record_audit(current_user, "local_ponto", saved.id, "rh.local_ponto.created", after=self._local_snapshot(saved))
        await self.uow.commit()
        await self._invalidate_cache_safely(current_user.team.id, funcionario.id)
        return saved

    async def update_local(self, local_id: UUID, dto: UpdateLocalPontoDTO, current_user: User) -> LocalPonto:
        self._ensure_rh_admin(current_user)
        local = await self.local_ponto_repo.get_by_id(local_id, current_user.team.id)
        before = self._local_snapshot(local)
        updated = LocalPonto(
            team_id=local.team_id,
            funcionario_id=local.funcionario_id,
            nome=dto.nome if dto.nome is not None else local.nome,
            latitude=dto.latitude if dto.latitude is not None else local.latitude,
            longitude=dto.longitude if dto.longitude is not None else local.longitude,
            raio_metros=dto.raio_metros if dto.raio_metros is not None else local.raio_metros,
            id=local.id,
        )
        saved = await self.local_ponto_repo.save(updated)
        await self._record_audit(
            current_user,
            "local_ponto",
            saved.id,
            "rh.local_ponto.updated",
            before=before,
            after=self._local_snapshot(saved),
        )
        await self.uow.commit()
        await self._invalidate_cache_safely(saved.team_id, saved.funcionario_id)
        return saved

    async def delete_local(self, local_id: UUID, current_user: User) -> None:
        self._ensure_rh_admin(current_user)
        local = await self.local_ponto_repo.get_by_id(local_id, current_user.team.id)
        before = self._local_snapshot(local)
        local.delete()
        await self.local_ponto_repo.save(local)
        await self._record_audit(current_user, "local_ponto", local.id, "rh.local_ponto.deleted", before=before)
        await self.uow.commit()
        await self._invalidate_cache_safely(local.team_id, local.funcionario_id)

    def _ensure_rh_admin(self, current_user: User) -> None:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")

    async def _record_audit(self, current_user: User, entity_type: str, entity_id: UUID, action: str, before=None, after=None) -> None:
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
            )
        )

    async def _invalidate_cache_safely(self, team_id: UUID, funcionario_id: UUID) -> None:
        try:
            await self.geofence_cache.invalidate(team_id, funcionario_id)
        except Exception:
            return None

    def _local_snapshot(self, local: LocalPonto) -> dict:
        return {
            "nome": local.nome,
            "latitude": local.latitude,
            "longitude": local.longitude,
            "raio_metros": local.raio_metros,
            "is_deleted": local.is_deleted,
        }


class RhPontoService:
    def __init__(
        self,
        funcionario_repo: FuncionarioRepository,
        local_ponto_repo: LocalPontoRepository,
        registro_ponto_repo: RegistroPontoRepository,
        audit_repo: RhAuditLogRepository,
        geofence_cache: RhGeofenceCache,
        idempotency_repo: RhIdempotencyKeyRepository | None,
        uow: UOWProvider,
    ) -> None:
        self.funcionario_repo = funcionario_repo
        self.local_ponto_repo = local_ponto_repo
        self.registro_ponto_repo = registro_ponto_repo
        self.audit_repo = audit_repo
        self.geofence_cache = geofence_cache
        self.idempotency_repo = idempotency_repo
        self.uow = uow

    async def registrar_ponto(
        self,
        dto: RegistrarPontoDTO,
        current_user: User,
        request_context: RequestContext,
    ) -> RegistroPonto:
        self._ensure_funcionario(current_user)
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None or not funcionario.is_active or funcionario.is_deleted:
            raise DomainError("Funcionario vinculado nao encontrado")
        await self._ensure_not_replayed(current_user.team.id, funcionario.id, dto.tipo, request_context.idempotency_key)
        locais = await self._load_locais(funcionario.team_id, funcionario.id)
        matched_local = self._match_local(locais, dto.latitude, dto.longitude)
        status = StatusPonto.VALIDADO
        denial_reason = None
        reference_timestamp = dto.client_timestamp.astimezone(timezone.utc) if dto.client_timestamp else datetime.now(timezone.utc)
        if locais and matched_local is None:
            status = StatusPonto.NEGADO
            denial_reason = "outside_geofence"
        else:
            if dto.client_timestamp is not None:
                last_on_day = await self.registro_ponto_repo.get_last_valid_on_day(
                    funcionario.team_id,
                    funcionario.id,
                    self._day_start(reference_timestamp),
                    self._day_end(reference_timestamp),
                )
            else:
                last_on_day = await self.registro_ponto_repo.get_last_valid_by_funcionario(
                    funcionario.team_id,
                    funcionario.id,
                )
            if self._is_inconsistent(dto.tipo, last_on_day):
                status = StatusPonto.INCONSISTENTE

        registro = RegistroPonto(
            team_id=funcionario.team_id,
            funcionario_id=funcionario.id,
            tipo=dto.tipo,
            timestamp=datetime.now(timezone.utc),
            latitude=dto.latitude,
            longitude=dto.longitude,
            status=status,
            local_ponto_id=matched_local.id if matched_local else None,
            client_timestamp=dto.client_timestamp,
            gps_accuracy_meters=dto.gps_accuracy_meters,
            device_fingerprint=dto.device_fingerprint,
            ip_hash=request_context.ip_hash,
            denial_reason=denial_reason,
        )
        saved = await self.registro_ponto_repo.save(registro)
        await self._record_audit(current_user, saved, request_context)
        await self.uow.commit()
        if saved.status == StatusPonto.NEGADO:
            raise DomainError("Voce esta fora de um local autorizado para registrar ponto.")
        return saved

    async def list_pontos(self, current_user: User, page: int, limit: int, funcionario_id=None, start=None, end=None, status=None):
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")
        start = start or datetime.min.replace(tzinfo=timezone.utc)
        end = end or datetime.max.replace(tzinfo=timezone.utc)
        if funcionario_id is None:
            if start == datetime.min.replace(tzinfo=timezone.utc) and end == datetime.max.replace(tzinfo=timezone.utc) and status is None:
                items = await self.registro_ponto_repo.list_by_team(current_user.team.id, page, limit)
                total = await self.registro_ponto_repo.count_by_team(current_user.team.id)
                return items, total
            items = await self.registro_ponto_repo.list_by_team_periodo(
                current_user.team.id,
                start,
                end,
                status=status,
                page=page,
                limit=limit,
            )
            total = await self.registro_ponto_repo.count_by_team_periodo(current_user.team.id, start, end, status=status)
            return items, total
        items = await self.registro_ponto_repo.list_by_funcionario_periodo(
            current_user.team.id,
            funcionario_id,
            start,
            end,
            status=status,
            page=page,
            limit=limit,
        )
        total = await self.registro_ponto_repo.count_by_funcionario_periodo(
            current_user.team.id,
            funcionario_id,
            start,
            end,
            status=status,
        )
        return items, total

    async def list_meus_pontos(self, current_user: User, page: int, limit: int, start=None, end=None, status=None):
        self._ensure_funcionario(current_user)
        funcionario = await self.funcionario_repo.get_by_user_id(current_user.team.id, current_user.id)
        if funcionario is None:
            raise DomainError("Funcionario vinculado nao encontrado")
        start = start or datetime.min.replace(tzinfo=timezone.utc)
        end = end or datetime.max.replace(tzinfo=timezone.utc)
        items = await self.registro_ponto_repo.list_by_funcionario_periodo(
            current_user.team.id,
            funcionario.id,
            start,
            end,
            status=status,
            page=page,
            limit=limit,
        )
        total = await self.registro_ponto_repo.count_by_funcionario_periodo(
            current_user.team.id,
            funcionario.id,
            start,
            end,
            status=status,
        )
        return items, total

    async def listar_dias_ponto(self, current_user: User, page: int, limit: int, funcionario_id=None, start=None, end=None, status=None):
        return await self.list_pontos(current_user, page, limit, funcionario_id=funcionario_id, start=start, end=end, status=status)

    async def obter_dia_ponto(self, current_user: User, funcionario_id: UUID, data: date) -> dict:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")
        funcionario = await self.funcionario_repo.get_by_id(funcionario_id, current_user.team.id)
        day_start = datetime.combine(data, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(data, time.max, tzinfo=timezone.utc)
        registros = await self.registro_ponto_repo.list_by_funcionario_day(current_user.team.id, funcionario.id, day_start, day_end)
        locais = await self.local_ponto_repo.list_by_funcionario(current_user.team.id, funcionario.id)
        status_dia = self._status_dia(registros)
        return {
            "funcionario": funcionario,
            "registros": registros,
            "status_dia": status_dia,
            "locais_autorizados": locais,
            "ajustes_relacionados": [],
            "impacto_estimado": self._impacto_estimado(registros),
            "auditoria_resumida": [],
        }

    async def obter_registro_ponto(self, current_user: User, registro_id: UUID) -> dict:
        if current_user.role not in {Roles.ADMIN, Roles.FINANCEIRO}:
            raise DomainError("Acesso restrito ao RH")
        registro = await self.registro_ponto_repo.get_by_id(registro_id, current_user.team.id)
        funcionario = await self.funcionario_repo.get_by_id(registro.funcionario_id, current_user.team.id)
        local = await self.local_ponto_repo.get_by_id(registro.local_ponto_id, current_user.team.id) if registro.local_ponto_id else None
        return {
            "registro": registro,
            "funcionario": funcionario,
            "local_ponto": local,
            "auditoria_resumida": [],
        }

    def _ensure_funcionario(self, current_user: User) -> None:
        if current_user.role != Roles.FUNCIONARIO:
            raise DomainError("Acesso restrito a funcionarios")

    async def _ensure_not_replayed(self, team_id: UUID, funcionario_id: UUID, tipo: TipoPonto, key: str | None) -> None:
        if not key or self.idempotency_repo is None:
            return
        scope = f"rh.ponto:{funcionario_id}:{tipo.value}"
        exists = await self.idempotency_repo.exists_or_create(team_id, scope, key)
        if exists:
            raise DomainError("Requisicao de ponto duplicada")

    async def _load_locais(self, team_id: UUID, funcionario_id: UUID) -> list[LocalPonto]:
        try:
            cached = await self.geofence_cache.get_locais(team_id, funcionario_id)
        except Exception:
            cached = None
        if cached is not None:
            return cached
        locais = await self.local_ponto_repo.list_by_funcionario(team_id, funcionario_id)
        try:
            await self.geofence_cache.set_locais(team_id, funcionario_id, locais)
        except Exception:
            return locais
        return locais

    def _match_local(self, locais: list[LocalPonto], latitude: float, longitude: float) -> LocalPonto | None:
        for local in locais:
            distance = haversine_distance_meters(latitude, longitude, local.latitude, local.longitude)
            if distance <= local.raio_metros:
                return local
        return None

    def _is_inconsistent(self, tipo: TipoPonto, last_on_day: RegistroPonto | None) -> bool:
        if last_on_day is None:
            return tipo == TipoPonto.SAIDA
        return last_on_day.tipo == tipo

    def _status_dia(self, registros: list[RegistroPonto]) -> str:
        if not registros:
            return "sem_registros"
        if any(item.status == StatusPonto.NEGADO for item in registros):
            return "com_negacao"
        if any(item.status == StatusPonto.INCONSISTENTE for item in registros):
            return "inconsistente"
        if len([item for item in registros if item.status in {StatusPonto.VALIDADO, StatusPonto.AJUSTADO}]) % 2:
            return "incompleto"
        return "validado"

    def _impacto_estimado(self, registros: list[RegistroPonto]) -> dict:
        return {
            "horas_extras_estimadas": "0.00",
            "faltas_estimadas": "0.00" if registros else "1.00",
        }

    async def _record_audit(self, current_user: User, registro: RegistroPonto, request_context: RequestContext) -> None:
        if registro.status == StatusPonto.NEGADO:
            action = "rh.ponto.denied"
        elif registro.status == StatusPonto.INCONSISTENTE:
            action = "rh.ponto.inconsistent"
        else:
            action = "rh.ponto.created"
        await self.audit_repo.save(
            RhAuditLog(
                team_id=current_user.team.id,
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
                entity_type="registro_ponto",
                entity_id=registro.id,
                action=action,
                after={
                    "tipo": registro.tipo.value,
                    "status": registro.status.value,
                    "funcionario_id": str(registro.funcionario_id),
                    "local_ponto_id": str(registro.local_ponto_id) if registro.local_ponto_id else None,
                },
                request_id=request_context.request_id,
                ip_hash=request_context.ip_hash,
                user_agent=request_context.user_agent,
            )
        )

    def _day_start(self, reference_timestamp: datetime) -> datetime:
        return datetime.combine(reference_timestamp.date(), time.min, tzinfo=timezone.utc)

    def _day_end(self, reference_timestamp: datetime) -> datetime:
        return datetime.combine(reference_timestamp.date(), time.max, tzinfo=timezone.utc)


def hash_ip(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
