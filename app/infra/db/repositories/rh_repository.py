from uuid import UUID, uuid4

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.providers.repo.rh_repo import (
    AjustePontoRepository,
    AtestadoRepository,
    FeriasRepository,
    FuncionarioRepository,
    HoleriteRepository,
    HorarioTrabalhoRepository,
    LocalPontoRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
    RhIdempotencyKeyRepository,
    RhSalarioHistoricoRepository,
    TipoAtestadoRepository,
)
from app.domain.entities.rh import (
    AjustePonto,
    Atestado,
    Ferias,
    Funcionario,
    Holerite,
    HorarioTrabalho,
    LocalPonto,
    RegistroPonto,
    RhAuditLog,
    RhIdempotencyKey,
    RhSalarioHistorico,
    StatusPonto,
    StatusAjuste,
    StatusAtestado,
    StatusFerias,
    StatusHolerite,
    TipoAtestado,
)
from app.domain.errors import DomainError
from app.infra.db.models.rh_model import (
    AjustePontoModel,
    AtestadoModel,
    FeriasModel,
    FuncionarioModel,
    HoleriteModel,
    HorarioTrabalhoModel,
    HorarioIntervaloModel,
    HorarioTurnoModel,
    LocalPontoModel,
    RegistroPontoModel,
    RhAuditLogModel,
    RhIdempotencyKeyModel,
    RhSalarioHistoricoModel,
    TipoAtestadoModel,
)


class FuncionarioRepositoryImpl(FuncionarioRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID) -> Funcionario:
        stmt = select(FuncionarioModel).where(
            FuncionarioModel.id == id,
            FuncionarioModel.team_id == team_id,
            FuncionarioModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Funcionario nao encontrado")
        return model.to_domain()

    async def get_by_cpf(self, team_id: UUID, cpf: str) -> Funcionario | None:
        stmt = select(FuncionarioModel).where(
            FuncionarioModel.team_id == team_id,
            FuncionarioModel.cpf == cpf,
            FuncionarioModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_user_id(self, team_id: UUID, user_id: UUID) -> Funcionario | None:
        stmt = select(FuncionarioModel).where(
            FuncionarioModel.team_id == team_id,
            FuncionarioModel.user_id == user_id,
            FuncionarioModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_by_team(
        self,
        team_id: UUID,
        page: int,
        limit: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> list[Funcionario]:
        stmt = select(FuncionarioModel).where(
            FuncionarioModel.team_id == team_id,
            FuncionarioModel.is_deleted == False,  # noqa: E712
        )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    FuncionarioModel.nome.ilike(pattern),
                    FuncionarioModel.cargo.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(FuncionarioModel.is_active == is_active)
        stmt = stmt.order_by(FuncionarioModel.nome.asc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_team(
        self,
        team_id: UUID,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(FuncionarioModel).where(
            FuncionarioModel.team_id == team_id,
            FuncionarioModel.is_deleted == False,  # noqa: E712
        )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    FuncionarioModel.nome.ilike(pattern),
                    FuncionarioModel.cargo.ilike(pattern),
                )
            )
        if is_active is not None:
            stmt = stmt.where(FuncionarioModel.is_active == is_active)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_active_by_team(self, team_id: UUID, limit: int, offset: int) -> list[Funcionario]:
        stmt = (
            select(FuncionarioModel)
            .where(
                FuncionarioModel.team_id == team_id,
                FuncionarioModel.is_active == True,  # noqa: E712
                FuncionarioModel.is_deleted == False,  # noqa: E712
            )
            .order_by(FuncionarioModel.nome.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def save(self, funcionario: Funcionario) -> Funcionario:
        stmt = select(FuncionarioModel).where(
            FuncionarioModel.id == funcionario.id,
            FuncionarioModel.team_id == funcionario.team_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = FuncionarioModel.from_domain(funcionario)
            self._session.add(model)
        else:
            model.update_from_domain(funcionario)
        await self._session.flush()
        return model.to_domain()


class HorarioTrabalhoRepositoryImpl(HorarioTrabalhoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID, team_id: UUID) -> HorarioTrabalho:
        stmt = (
            select(HorarioTrabalhoModel)
            .options(selectinload(HorarioTrabalhoModel.turnos).selectinload(HorarioTurnoModel.intervalos))
            .where(
                HorarioTrabalhoModel.id == id,
                HorarioTrabalhoModel.team_id == team_id,
                HorarioTrabalhoModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Horario de trabalho nao encontrado")
        return model.to_domain()

    async def get_by_funcionario_id(self, team_id: UUID, funcionario_id: UUID) -> HorarioTrabalho | None:
        stmt = (
            select(HorarioTrabalhoModel)
            .options(selectinload(HorarioTrabalhoModel.turnos).selectinload(HorarioTurnoModel.intervalos))
            .where(
                HorarioTrabalhoModel.team_id == team_id,
                HorarioTrabalhoModel.funcionario_id == funcionario_id,
                HorarioTrabalhoModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_by_funcionarios(self, team_id: UUID, funcionario_ids: list[UUID]) -> dict[UUID, HorarioTrabalho]:
        if not funcionario_ids:
            return {}
        stmt = (
            select(HorarioTrabalhoModel)
            .options(selectinload(HorarioTrabalhoModel.turnos).selectinload(HorarioTurnoModel.intervalos))
            .where(
                HorarioTrabalhoModel.team_id == team_id,
                HorarioTrabalhoModel.funcionario_id.in_(funcionario_ids),
                HorarioTrabalhoModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        return {model.funcionario_id: model.to_domain() for model in result.scalars().all()}

    async def save(self, horario: HorarioTrabalho) -> HorarioTrabalho:
        stmt = (
            select(HorarioTrabalhoModel)
            .options(selectinload(HorarioTrabalhoModel.turnos).selectinload(HorarioTurnoModel.intervalos))
            .where(
                HorarioTrabalhoModel.id == horario.id,
                HorarioTrabalhoModel.team_id == horario.team_id,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = HorarioTrabalhoModel.from_domain(horario)
            self._session.add(model)
            await self._session.flush()
        else:
            model.update_from_domain(horario)
            for turno_model in list(model.turnos):
                await self._session.delete(turno_model)
            await self._session.flush()

        for turno in horario.turnos:
            turno_model = HorarioTurnoModel.from_domain(model.id, turno)
            self._session.add(turno_model)
            await self._session.flush()
            for ordem, intervalo in enumerate(turno.intervalos):
                self._session.add(HorarioIntervaloModel.from_domain(turno_model.id, intervalo, ordem))
        await self._session.flush()
        return await self.get_by_id(model.id, horario.team_id)


class _SoftDeleteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_by_id(self, model_cls, id: UUID, team_id: UUID, message: str):
        stmt = select(model_cls).where(
            model_cls.id == id,
            model_cls.team_id == team_id,
            model_cls.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError(message)
        return model

    async def _list_by_team(self, model_cls, team_id: UUID, page: int, limit: int):
        stmt = (
            select(model_cls)
            .where(model_cls.team_id == team_id, model_cls.is_deleted == False)  # noqa: E712
            .order_by(model_cls.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def _save(self, entity, model_cls, not_found_message: str):
        stmt = select(model_cls).where(model_cls.id == entity.id, model_cls.team_id == entity.team_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = model_cls.from_domain(entity)
            self._session.add(model)
        else:
            model.update_from_domain(entity)
        await self._session.flush()
        return model.to_domain()


class FeriasRepositoryImpl(_SoftDeleteRepository, FeriasRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> Ferias:
        return (await self._get_by_id(FeriasModel, id, team_id, "Ferias nao encontradas")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Ferias]:
        return await self._list_by_team(FeriasModel, team_id, page, limit)

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[Ferias]:
        stmt = self._ferias_filters(select(FeriasModel), team_id, **filters)
        stmt = stmt.order_by(FeriasModel.data_inicio.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._ferias_filters(select(func.count()).select_from(FeriasModel), team_id, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def has_overlap(self, team_id: UUID, funcionario_id: UUID, start, end, statuses, exclude_id: UUID | None = None) -> bool:
        status_values = [status.value if hasattr(status, "value") else str(status) for status in statuses]
        stmt = select(func.count()).select_from(FeriasModel).where(
            FeriasModel.team_id == team_id,
            FeriasModel.funcionario_id == funcionario_id,
            FeriasModel.is_deleted == False,  # noqa: E712
            FeriasModel.status.in_(status_values),
            FeriasModel.data_inicio < end,
            FeriasModel.data_fim > start,
        )
        if exclude_id is not None:
            stmt = stmt.where(FeriasModel.id != exclude_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one()) > 0

    async def save(self, ferias: Ferias) -> Ferias:
        return await self._save(ferias, FeriasModel, "Ferias nao encontradas para atualizacao")

    async def list_by_competencia(self, team_id: UUID, funcionario_ids: list[UUID], start, end, statuses) -> list[Ferias]:
        if not funcionario_ids:
            return []
        status_values = [status.value if hasattr(status, "value") else str(status) for status in statuses]
        stmt = (
            select(FeriasModel)
            .where(
                FeriasModel.team_id == team_id,
                FeriasModel.funcionario_id.in_(funcionario_ids),
                FeriasModel.is_deleted == False,  # noqa: E712
                FeriasModel.status.in_(status_values),
                FeriasModel.data_inicio <= end,
                FeriasModel.data_fim >= start,
            )
            .order_by(FeriasModel.data_inicio.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    def _ferias_filters(self, stmt, team_id: UUID, **filters):
        stmt = stmt.where(FeriasModel.team_id == team_id, FeriasModel.is_deleted == False)  # noqa: E712
        funcionario_id = filters.get("funcionario_id")
        status = filters.get("status")
        start = filters.get("start")
        end = filters.get("end")
        if funcionario_id:
            stmt = stmt.where(FeriasModel.funcionario_id == funcionario_id)
        if status:
            stmt = stmt.where(FeriasModel.status == (status.value if hasattr(status, "value") else str(status)))
        if start:
            stmt = stmt.where(FeriasModel.data_fim >= start)
        if end:
            stmt = stmt.where(FeriasModel.data_inicio <= end)
        return stmt


class LocalPontoRepositoryImpl(_SoftDeleteRepository, LocalPontoRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> LocalPonto:
        return (await self._get_by_id(LocalPontoModel, id, team_id, "Local de ponto nao encontrado")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[LocalPonto]:
        return await self._list_by_team(LocalPontoModel, team_id, page, limit)

    async def list_by_funcionario(self, team_id: UUID, funcionario_id: UUID) -> list[LocalPonto]:
        stmt = (
            select(LocalPontoModel)
            .where(
                LocalPontoModel.team_id == team_id,
                LocalPontoModel.funcionario_id == funcionario_id,
                LocalPontoModel.is_deleted == False,  # noqa: E712
            )
            .order_by(LocalPontoModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def save(self, local_ponto: LocalPonto) -> LocalPonto:
        return await self._save(local_ponto, LocalPontoModel, "Local de ponto nao encontrado para atualizacao")


class RegistroPontoRepositoryImpl(_SoftDeleteRepository, RegistroPontoRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> RegistroPonto:
        return (await self._get_by_id(RegistroPontoModel, id, team_id, "Registro de ponto nao encontrado")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[RegistroPonto]:
        return await self._list_by_team(RegistroPontoModel, team_id, page, limit)

    async def count_by_team(self, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(RegistroPontoModel).where(
            RegistroPontoModel.team_id == team_id,
            RegistroPontoModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_by_team_periodo(
        self,
        team_id: UUID,
        start: datetime,
        end: datetime,
        status=None,
        page: int = 1,
        limit: int = 50,
    ) -> list[RegistroPonto]:
        stmt = (
            select(RegistroPontoModel)
            .where(
                RegistroPontoModel.team_id == team_id,
                RegistroPontoModel.timestamp >= start,
                RegistroPontoModel.timestamp <= end,
                RegistroPontoModel.is_deleted == False,  # noqa: E712
            )
            .order_by(RegistroPontoModel.timestamp.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        if status is not None:
            status_value = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(RegistroPontoModel.status == status_value)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def list_by_funcionario_periodo(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        start: datetime,
        end: datetime,
        status=None,
        page: int = 1,
        limit: int = 50,
    ) -> list[RegistroPonto]:
        stmt = (
            select(RegistroPontoModel)
            .where(
                RegistroPontoModel.team_id == team_id,
                RegistroPontoModel.funcionario_id == funcionario_id,
                RegistroPontoModel.timestamp >= start,
                RegistroPontoModel.timestamp <= end,
                RegistroPontoModel.is_deleted == False,  # noqa: E712
            )
            .order_by(RegistroPontoModel.timestamp.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        if status is not None:
            status_value = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(RegistroPontoModel.status == status_value)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_funcionario_periodo(self, team_id: UUID, funcionario_id: UUID, start: datetime, end: datetime, status=None) -> int:
        stmt = select(func.count()).select_from(RegistroPontoModel).where(
            RegistroPontoModel.team_id == team_id,
            RegistroPontoModel.funcionario_id == funcionario_id,
            RegistroPontoModel.timestamp >= start,
            RegistroPontoModel.timestamp <= end,
            RegistroPontoModel.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            status_value = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(RegistroPontoModel.status == status_value)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_by_team_periodo(self, team_id: UUID, start: datetime, end: datetime, status=None) -> int:
        stmt = select(func.count()).select_from(RegistroPontoModel).where(
            RegistroPontoModel.team_id == team_id,
            RegistroPontoModel.timestamp >= start,
            RegistroPontoModel.timestamp <= end,
            RegistroPontoModel.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            status_value = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(RegistroPontoModel.status == status_value)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_last_valid_by_funcionario(self, team_id: UUID, funcionario_id: UUID) -> RegistroPonto | None:
        stmt = (
            select(RegistroPontoModel)
            .where(
                RegistroPontoModel.team_id == team_id,
                RegistroPontoModel.funcionario_id == funcionario_id,
                RegistroPontoModel.is_deleted == False,  # noqa: E712
                RegistroPontoModel.status.in_(
                    [StatusPonto.VALIDADO.value, StatusPonto.INCONSISTENTE.value, StatusPonto.AJUSTADO.value]
                ),
            )
            .order_by(RegistroPontoModel.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_last_valid_on_day(self, team_id: UUID, funcionario_id: UUID, day_start, day_end) -> RegistroPonto | None:
        stmt = (
            select(RegistroPontoModel)
            .where(
                RegistroPontoModel.team_id == team_id,
                RegistroPontoModel.funcionario_id == funcionario_id,
                RegistroPontoModel.timestamp >= day_start,
                RegistroPontoModel.timestamp <= day_end,
                RegistroPontoModel.is_deleted == False,  # noqa: E712
                RegistroPontoModel.status.in_(
                    [StatusPonto.VALIDADO.value, StatusPonto.INCONSISTENTE.value, StatusPonto.AJUSTADO.value]
                ),
            )
            .order_by(RegistroPontoModel.timestamp.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_by_funcionario_day(self, team_id: UUID, funcionario_id: UUID, day_start, day_end) -> list[RegistroPonto]:
        stmt = (
            select(RegistroPontoModel)
            .where(
                RegistroPontoModel.team_id == team_id,
                RegistroPontoModel.funcionario_id == funcionario_id,
                RegistroPontoModel.timestamp >= day_start,
                RegistroPontoModel.timestamp <= day_end,
                RegistroPontoModel.is_deleted == False,  # noqa: E712
            )
            .order_by(RegistroPontoModel.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def list_by_competencia(self, team_id: UUID, funcionario_ids: list[UUID], start, end) -> list[RegistroPonto]:
        if not funcionario_ids:
            return []
        stmt = (
            select(RegistroPontoModel)
            .where(
                RegistroPontoModel.team_id == team_id,
                RegistroPontoModel.funcionario_id.in_(funcionario_ids),
                RegistroPontoModel.timestamp >= start,
                RegistroPontoModel.timestamp <= end,
                RegistroPontoModel.is_deleted == False,  # noqa: E712
            )
            .order_by(RegistroPontoModel.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def save(self, registro: RegistroPonto) -> RegistroPonto:
        return await self._save(registro, RegistroPontoModel, "Registro de ponto nao encontrado para atualizacao")


class AjustePontoRepositoryImpl(_SoftDeleteRepository, AjustePontoRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> AjustePonto:
        return (await self._get_by_id(AjustePontoModel, id, team_id, "Ajuste de ponto nao encontrado")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[AjustePonto]:
        return await self._list_by_team(AjustePontoModel, team_id, page, limit)

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[AjustePonto]:
        stmt = self._ajuste_filters(select(AjustePontoModel), team_id, **filters)
        stmt = stmt.order_by(AjustePontoModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._ajuste_filters(select(func.count()).select_from(AjustePontoModel), team_id, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def has_pending_duplicate(self, team_id: UUID, funcionario_id: UUID, data_referencia, entrada, saida) -> bool:
        stmt = select(func.count()).select_from(AjustePontoModel).where(
            AjustePontoModel.team_id == team_id,
            AjustePontoModel.funcionario_id == funcionario_id,
            AjustePontoModel.data_referencia == data_referencia,
            AjustePontoModel.status == StatusAjuste.PENDENTE.value,
            AjustePontoModel.is_deleted == False,  # noqa: E712
        )
        if entrada is None:
            stmt = stmt.where(AjustePontoModel.hora_entrada_solicitada.is_(None))
        else:
            stmt = stmt.where(AjustePontoModel.hora_entrada_solicitada == entrada)
        if saida is None:
            stmt = stmt.where(AjustePontoModel.hora_saida_solicitada.is_(None))
        else:
            stmt = stmt.where(AjustePontoModel.hora_saida_solicitada == saida)
        result = await self._session.execute(stmt)
        return int(result.scalar_one()) > 0

    async def save(self, ajuste: AjustePonto) -> AjustePonto:
        return await self._save(ajuste, AjustePontoModel, "Ajuste de ponto nao encontrado para atualizacao")

    def _ajuste_filters(self, stmt, team_id: UUID, **filters):
        stmt = stmt.where(AjustePontoModel.team_id == team_id, AjustePontoModel.is_deleted == False)  # noqa: E712
        funcionario_id = filters.get("funcionario_id")
        status = filters.get("status")
        start = filters.get("start")
        end = filters.get("end")
        if funcionario_id:
            stmt = stmt.where(AjustePontoModel.funcionario_id == funcionario_id)
        if status:
            stmt = stmt.where(AjustePontoModel.status == (status.value if hasattr(status, "value") else str(status)))
        if start:
            stmt = stmt.where(AjustePontoModel.data_referencia >= start)
        if end:
            stmt = stmt.where(AjustePontoModel.data_referencia <= end)
        return stmt


class TipoAtestadoRepositoryImpl(_SoftDeleteRepository, TipoAtestadoRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> TipoAtestado:
        return (await self._get_by_id(TipoAtestadoModel, id, team_id, "Tipo de atestado nao encontrado")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[TipoAtestado]:
        return await self._list_by_team(TipoAtestadoModel, team_id, page, limit)

    async def list_active(self, team_id: UUID, page: int, limit: int) -> list[TipoAtestado]:
        return await self._list_by_team(TipoAtestadoModel, team_id, page, limit)

    async def count_active(self, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(TipoAtestadoModel).where(
            TipoAtestadoModel.team_id == team_id,
            TipoAtestadoModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def save(self, tipo_atestado: TipoAtestado) -> TipoAtestado:
        return await self._save(tipo_atestado, TipoAtestadoModel, "Tipo de atestado nao encontrado para atualizacao")


class AtestadoRepositoryImpl(_SoftDeleteRepository, AtestadoRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> Atestado:
        return (await self._get_by_id(AtestadoModel, id, team_id, "Atestado nao encontrado")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Atestado]:
        return await self._list_by_team(AtestadoModel, team_id, page, limit)

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[Atestado]:
        stmt = self._atestado_filters(select(AtestadoModel), team_id, **filters)
        stmt = stmt.order_by(AtestadoModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._atestado_filters(select(func.count()).select_from(AtestadoModel), team_id, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_due_for_expiration(self, now, limit: int = 500, team_id: UUID | None = None) -> list[Atestado]:
        stmt = (
            select(AtestadoModel)
            .where(
                AtestadoModel.status == StatusAtestado.AGUARDANDO_ENTREGA.value,
                AtestadoModel.is_deleted == False,  # noqa: E712
            )
            .order_by(AtestadoModel.created_at.asc())
            .limit(limit)
        )
        if team_id is not None:
            stmt = stmt.where(AtestadoModel.team_id == team_id)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def save(self, atestado: Atestado) -> Atestado:
        return await self._save(atestado, AtestadoModel, "Atestado nao encontrado para atualizacao")

    async def list_by_competencia(self, team_id: UUID, funcionario_ids: list[UUID], start, end, statuses) -> list[Atestado]:
        if not funcionario_ids:
            return []
        status_values = [status.value if hasattr(status, "value") else str(status) for status in statuses]
        stmt = (
            select(AtestadoModel)
            .where(
                AtestadoModel.team_id == team_id,
                AtestadoModel.funcionario_id.in_(funcionario_ids),
                AtestadoModel.is_deleted == False,  # noqa: E712
                AtestadoModel.status.in_(status_values),
                AtestadoModel.data_inicio <= end,
                AtestadoModel.data_fim >= start,
            )
            .order_by(AtestadoModel.data_inicio.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    def _atestado_filters(self, stmt, team_id: UUID, **filters):
        stmt = stmt.where(AtestadoModel.team_id == team_id, AtestadoModel.is_deleted == False)  # noqa: E712
        funcionario_id = filters.get("funcionario_id")
        tipo_atestado_id = filters.get("tipo_atestado_id")
        status = filters.get("status")
        start = filters.get("start")
        end = filters.get("end")
        if funcionario_id:
            stmt = stmt.where(AtestadoModel.funcionario_id == funcionario_id)
        if tipo_atestado_id:
            stmt = stmt.where(AtestadoModel.tipo_atestado_id == tipo_atestado_id)
        if status:
            stmt = stmt.where(AtestadoModel.status == (status.value if hasattr(status, "value") else str(status)))
        if start:
            stmt = stmt.where(AtestadoModel.data_fim >= start)
        if end:
            stmt = stmt.where(AtestadoModel.data_inicio <= end)
        return stmt


class HoleriteRepositoryImpl(_SoftDeleteRepository, HoleriteRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> Holerite:
        return (await self._get_by_id(HoleriteModel, id, team_id, "Holerite nao encontrado")).to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Holerite]:
        return await self._list_by_team(HoleriteModel, team_id, page, limit)

    async def get_by_competencia(self, team_id: UUID, funcionario_id: UUID, mes: int, ano: int) -> Holerite | None:
        stmt = select(HoleriteModel).where(
            HoleriteModel.team_id == team_id,
            HoleriteModel.funcionario_id == funcionario_id,
            HoleriteModel.mes_referencia == mes,
            HoleriteModel.ano_referencia == ano,
            HoleriteModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_by_competencia(
        self,
        team_id: UUID,
        mes: int,
        ano: int,
        status=None,
        page: int = 1,
        limit: int = 50,
        funcionario_id: UUID | None = None,
    ) -> list[Holerite]:
        stmt = select(HoleriteModel).where(
            HoleriteModel.team_id == team_id,
            HoleriteModel.mes_referencia == mes,
            HoleriteModel.ano_referencia == ano,
            HoleriteModel.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            status_value = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(HoleriteModel.status == status_value)
        if funcionario_id is not None:
            stmt = stmt.where(HoleriteModel.funcionario_id == funcionario_id)
        stmt = stmt.order_by(HoleriteModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_competencia(self, team_id: UUID, mes: int, ano: int, status=None, funcionario_id: UUID | None = None) -> int:
        stmt = select(func.count()).select_from(HoleriteModel).where(
            HoleriteModel.team_id == team_id,
            HoleriteModel.mes_referencia == mes,
            HoleriteModel.ano_referencia == ano,
            HoleriteModel.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            status_value = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(HoleriteModel.status == status_value)
        if funcionario_id is not None:
            stmt = stmt.where(HoleriteModel.funcionario_id == funcionario_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_rascunhos_by_competencia(
        self,
        team_id: UUID,
        mes: int,
        ano: int,
        limit: int = 500,
        funcionario_ids: list[UUID] | None = None,
    ) -> list[Holerite]:
        stmt = (
            select(HoleriteModel)
            .where(
                HoleriteModel.team_id == team_id,
                HoleriteModel.mes_referencia == mes,
                HoleriteModel.ano_referencia == ano,
                HoleriteModel.status == StatusHolerite.RASCUNHO.value,
                HoleriteModel.is_deleted == False,  # noqa: E712
            )
            .order_by(HoleriteModel.created_at.asc())
            .limit(limit)
        )
        if funcionario_ids:
            stmt = stmt.where(HoleriteModel.funcionario_id.in_(funcionario_ids))
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def list_by_funcionario(self, team_id: UUID, funcionario_id: UUID, page: int, limit: int) -> list[Holerite]:
        stmt = (
            select(HoleriteModel)
            .where(
                HoleriteModel.team_id == team_id,
                HoleriteModel.funcionario_id == funcionario_id,
                HoleriteModel.is_deleted == False,  # noqa: E712
            )
            .order_by(HoleriteModel.ano_referencia.desc(), HoleriteModel.mes_referencia.desc(), HoleriteModel.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_funcionario(self, team_id: UUID, funcionario_id: UUID) -> int:
        stmt = select(func.count()).select_from(HoleriteModel).where(
            HoleriteModel.team_id == team_id,
            HoleriteModel.funcionario_id == funcionario_id,
            HoleriteModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def summarize_by_competencia(self, team_id: UUID, mes: int, ano: int) -> dict:
        stmt = (
            select(
                HoleriteModel.status,
                func.count(HoleriteModel.id),
                func.coalesce(func.sum(HoleriteModel.valor_liquido_amount), 0),
            )
            .where(
                HoleriteModel.team_id == team_id,
                HoleriteModel.mes_referencia == mes,
                HoleriteModel.ano_referencia == ano,
                HoleriteModel.is_deleted == False,  # noqa: E712
            )
            .group_by(HoleriteModel.status)
        )
        result = await self._session.execute(stmt)
        summary = {"total_liquido": 0}
        for status, count, total_liquido in result.all():
            summary[status] = int(count)
            summary["total_liquido"] += total_liquido
        return summary

    async def save(self, holerite: Holerite) -> Holerite:
        return await self._save(holerite, HoleriteModel, "Holerite nao encontrado para atualizacao")


class RhAuditLogRepositoryImpl(RhAuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, audit_log: RhAuditLog) -> RhAuditLog:
        if audit_log.id is None:
            audit_log.id = uuid4()
        model = RhAuditLogModel.from_domain(audit_log)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[RhAuditLog]:
        stmt = self._build_filters(select(RhAuditLogModel), team_id, **filters)
        stmt = stmt.order_by(RhAuditLogModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._build_filters(select(func.count()).select_from(RhAuditLogModel), team_id, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    def _build_filters(self, stmt, team_id: UUID, **filters):
        stmt = stmt.where(RhAuditLogModel.team_id == team_id)
        if filters.get("entity_type"):
            stmt = stmt.where(RhAuditLogModel.entity_type == filters["entity_type"])
        if filters.get("entity_id"):
            stmt = stmt.where(RhAuditLogModel.entity_id == filters["entity_id"])
        if filters.get("actor_user_id"):
            stmt = stmt.where(RhAuditLogModel.actor_user_id == filters["actor_user_id"])
        if filters.get("action"):
            stmt = stmt.where(RhAuditLogModel.action == filters["action"])
        if filters.get("start"):
            stmt = stmt.where(RhAuditLogModel.created_at >= filters["start"])
        if filters.get("end"):
            stmt = stmt.where(RhAuditLogModel.created_at <= filters["end"])
        return stmt


class RhIdempotencyKeyRepositoryImpl(RhIdempotencyKeyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_key(self, team_id: UUID, scope: str, key: str) -> RhIdempotencyKey | None:
        stmt = select(RhIdempotencyKeyModel).where(
            RhIdempotencyKeyModel.team_id == team_id,
            RhIdempotencyKeyModel.scope == scope,
            RhIdempotencyKeyModel.key == key,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def exists_or_create(self, team_id: UUID, scope: str, key: str) -> bool:
        existing = await self.get_by_key(team_id, scope, key)
        if existing:
            return True
        try:
            async with self._session.begin_nested():
                model = RhIdempotencyKeyModel.from_domain(
                    RhIdempotencyKey(team_id=team_id, scope=scope, key=key)
                )
                self._session.add(model)
                await self._session.flush()
            return False
        except IntegrityError:
            return True


class RhSalarioHistoricoRepositoryImpl(RhSalarioHistoricoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, historico: RhSalarioHistorico) -> RhSalarioHistorico:
        model = RhSalarioHistoricoModel(
            id=historico.id,
            team_id=historico.team_id,
            funcionario_id=historico.funcionario_id,
            salario_anterior_amount=historico.salario_anterior.amount,
            salario_anterior_currency=historico.salario_anterior.currency,
            salario_novo_amount=historico.salario_novo.amount,
            salario_novo_currency=historico.salario_novo.currency,
            changed_by_user_id=historico.changed_by_user_id,
            reason=historico.reason,
            created_at=historico.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()
