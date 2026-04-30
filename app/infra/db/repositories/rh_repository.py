from uuid import UUID, uuid4

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.providers.repo.rh_repo import (
    AjustePontoRepository,
    AtestadoRepository,
    BeneficioRepository,
    FaixaEncargoRepository,
    FeriasRepository,
    FuncionarioRepository,
    HoleriteRepository,
    HoleriteItemRepository,
    HorarioTrabalhoRepository,
    LocalPontoRepository,
    RegraEncargoRepository,
    RegistroPontoRepository,
    RhAuditLogRepository,
    RhFolhaJobRepository,
    RhIdempotencyKeyRepository,
    RhSalarioHistoricoRepository,
    TabelaProgressivaRepository,
    TipoAtestadoRepository,
)
from app.domain.entities.rh import (
    AjustePonto,
    Atestado,
    Beneficio,
    FaixaEncargo,
    Ferias,
    Funcionario,
    Holerite,
    HoleriteItem,
    HorarioTrabalho,
    LocalPonto,
    RegraEncargo,
    RegistroPonto,
    RhAuditLog,
    RhFolhaJob,
    RhIdempotencyKey,
    RhSalarioHistorico,
    StatusPonto,
    StatusAjuste,
    StatusAtestado,
    StatusFerias,
    StatusHolerite,
    StatusBeneficio,
    StatusRegraEncargo,
    TabelaProgressiva,
    TipoAtestado,
)
from app.domain.errors import DomainError
from app.infra.db.models.rh_model import (
    AjustePontoModel,
    AtestadoModel,
    BeneficioModel,
    FaixaEncargoModel,
    FeriasModel,
    FuncionarioModel,
    HoleriteModel,
    HoleriteItemModel,
    HorarioTrabalhoModel,
    HorarioIntervaloModel,
    HorarioTurnoModel,
    LocalPontoModel,
    RegraEncargoAplicabilidadeModel,
    RegraEncargoModel,
    RegistroPontoModel,
    RhAuditLogModel,
    RhFolhaJobModel,
    RhIdempotencyKeyModel,
    RhSalarioHistoricoModel,
    TabelaProgressivaModel,
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


class BeneficioRepositoryImpl(_SoftDeleteRepository, BeneficioRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> Beneficio:
        return (await self._get_by_id(BeneficioModel, id, team_id, "Beneficio nao encontrado")).to_domain()

    async def get_active_by_nome(self, team_id: UUID, nome: str) -> Beneficio | None:
        stmt = select(BeneficioModel).where(
            BeneficioModel.team_id == team_id,
            func.lower(BeneficioModel.nome) == nome.strip().lower(),
            BeneficioModel.status == "ativo",
            BeneficioModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[Beneficio]:
        stmt = self._build_filters(select(BeneficioModel), team_id, **filters)
        stmt = stmt.order_by(BeneficioModel.nome.asc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._build_filters(select(func.count()).select_from(BeneficioModel), team_id, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def save(self, beneficio: Beneficio) -> Beneficio:
        return await self._save(beneficio, BeneficioModel, "Beneficio nao encontrado para atualizacao")

    def _build_filters(self, stmt, team_id: UUID, **filters):
        stmt = stmt.where(
            BeneficioModel.team_id == team_id,
            BeneficioModel.is_deleted == False,  # noqa: E712
        )
        if filters.get("status") is not None:
            status = filters["status"]
            stmt = stmt.where(BeneficioModel.status == (status.value if hasattr(status, "value") else str(status)))
        if filters.get("search"):
            pattern = f"%{filters['search'].strip()}%"
            stmt = stmt.where(BeneficioModel.nome.ilike(pattern))
        return stmt


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


class TabelaProgressivaRepositoryImpl(_SoftDeleteRepository, TabelaProgressivaRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> TabelaProgressiva:
        stmt = (
            select(TabelaProgressivaModel)
            .options(selectinload(TabelaProgressivaModel.faixas))
            .where(
                TabelaProgressivaModel.id == id,
                TabelaProgressivaModel.team_id == team_id,
                TabelaProgressivaModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Tabela progressiva nao encontrada")
        return model.to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[TabelaProgressiva]:
        stmt = self._build_filters(select(TabelaProgressivaModel), team_id)
        stmt = stmt.order_by(TabelaProgressivaModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[TabelaProgressiva]:
        stmt = self._build_filters(select(TabelaProgressivaModel), team_id, **filters)
        stmt = stmt.order_by(TabelaProgressivaModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._build_filters(select(func.count()).select_from(TabelaProgressivaModel), team_id, load_faixas=False, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def is_used_by_active_rule(self, team_id: UUID, tabela_id: UUID) -> bool:
        stmt = select(func.count()).select_from(RegraEncargoModel).where(
            RegraEncargoModel.team_id == team_id,
            RegraEncargoModel.tabela_progressiva_id == tabela_id,
            RegraEncargoModel.status == StatusRegraEncargo.ATIVA.value,
            RegraEncargoModel.is_deleted == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one()) > 0

    def _build_filters(self, stmt, team_id: UUID, load_faixas: bool = True, **filters):
        if load_faixas:
            stmt = stmt.options(selectinload(TabelaProgressivaModel.faixas))
        stmt = stmt.where(
            TabelaProgressivaModel.team_id == team_id,
            TabelaProgressivaModel.is_deleted == False,  # noqa: E712
        )
        if filters.get("search"):
            pattern = f"%{filters['search'].strip()}%"
            stmt = stmt.where(or_(TabelaProgressivaModel.codigo.ilike(pattern), TabelaProgressivaModel.nome.ilike(pattern)))
        if filters.get("codigo"):
            stmt = stmt.where(TabelaProgressivaModel.codigo == filters["codigo"])
        if filters.get("status"):
            status = filters["status"]
            stmt = stmt.where(TabelaProgressivaModel.status == (status.value if hasattr(status, "value") else str(status)))
        return stmt

    async def save(self, tabela: TabelaProgressiva) -> TabelaProgressiva:
        stmt = (
            select(TabelaProgressivaModel)
            .options(selectinload(TabelaProgressivaModel.faixas))
            .where(TabelaProgressivaModel.id == tabela.id, TabelaProgressivaModel.team_id == tabela.team_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = TabelaProgressivaModel(
                id=tabela.id,
                team_id=tabela.team_id,
                codigo=tabela.codigo,
                nome=tabela.nome,
                descricao=tabela.descricao,
                vigencia_inicio=tabela.vigencia_inicio,
                vigencia_fim=tabela.vigencia_fim,
                status=tabela.status.value,
                created_by_user_id=tabela.created_by_user_id,
                approved_by_user_id=tabela.approved_by_user_id,
                is_deleted=tabela.is_deleted,
            )
            self._session.add(model)
            await self._session.flush()
        else:
            model.codigo = tabela.codigo
            model.nome = tabela.nome
            model.descricao = tabela.descricao
            model.vigencia_inicio = tabela.vigencia_inicio
            model.vigencia_fim = tabela.vigencia_fim
            model.status = tabela.status.value
            model.created_by_user_id = tabela.created_by_user_id
            model.approved_by_user_id = tabela.approved_by_user_id
            model.is_deleted = tabela.is_deleted
            for faixa_model in list(model.faixas):
                await self._session.delete(faixa_model)
            await self._session.flush()

        for faixa in tabela.faixas:
            self._session.add(
                FaixaEncargoModel(
                    id=faixa.id,
                    team_id=faixa.team_id,
                    tabela_progressiva_id=model.id,
                    ordem=faixa.ordem,
                    valor_inicial_amount=faixa.valor_inicial.amount,
                    valor_inicial_currency=faixa.valor_inicial.currency,
                    valor_final_amount=faixa.valor_final.amount if faixa.valor_final else None,
                    valor_final_currency=faixa.valor_final.currency if faixa.valor_final else None,
                    aliquota=faixa.aliquota,
                    deducao_amount=faixa.deducao.amount,
                    deducao_currency=faixa.deducao.currency,
                    calculo_marginal=faixa.calculo_marginal,
                )
            )
        await self._session.flush()
        return await self.get_by_id(model.id, tabela.team_id)


class FaixaEncargoRepositoryImpl(FaixaEncargoRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_by_tabela(self, team_id: UUID, tabela_id: UUID, faixas: list[FaixaEncargo]) -> list[FaixaEncargo]:
        stmt = select(FaixaEncargoModel).where(
            FaixaEncargoModel.team_id == team_id,
            FaixaEncargoModel.tabela_progressiva_id == tabela_id,
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._session.delete(model)
        await self._session.flush()
        for faixa in faixas:
            self._session.add(
                FaixaEncargoModel(
                    id=faixa.id,
                    team_id=faixa.team_id,
                    tabela_progressiva_id=tabela_id,
                    ordem=faixa.ordem,
                    valor_inicial_amount=faixa.valor_inicial.amount,
                    valor_inicial_currency=faixa.valor_inicial.currency,
                    valor_final_amount=faixa.valor_final.amount if faixa.valor_final else None,
                    valor_final_currency=faixa.valor_final.currency if faixa.valor_final else None,
                    aliquota=faixa.aliquota,
                    deducao_amount=faixa.deducao.amount,
                    deducao_currency=faixa.deducao.currency,
                    calculo_marginal=faixa.calculo_marginal,
                )
            )
        await self._session.flush()
        return faixas


class RegraEncargoRepositoryImpl(_SoftDeleteRepository, RegraEncargoRepository):
    async def get_by_id(self, id: UUID, team_id: UUID) -> RegraEncargo:
        stmt = (
            select(RegraEncargoModel)
            .options(
                selectinload(RegraEncargoModel.aplicabilidades),
                selectinload(RegraEncargoModel.tabela_progressiva).selectinload(TabelaProgressivaModel.faixas),
            )
            .where(
                RegraEncargoModel.id == id,
                RegraEncargoModel.team_id == team_id,
                RegraEncargoModel.is_deleted == False,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise DomainError("Regra de encargo nao encontrada")
        return model.to_domain()

    async def list_active_by_competencia(self, team_id: UUID, competencia) -> list[RegraEncargo]:
        stmt = (
            select(RegraEncargoModel)
            .options(
                selectinload(RegraEncargoModel.aplicabilidades),
                selectinload(RegraEncargoModel.tabela_progressiva).selectinload(TabelaProgressivaModel.faixas),
            )
            .where(
                RegraEncargoModel.team_id == team_id,
                RegraEncargoModel.status == StatusRegraEncargo.ATIVA.value,
                RegraEncargoModel.is_deleted == False,  # noqa: E712
                RegraEncargoModel.vigencia_inicio <= competencia,
                or_(RegraEncargoModel.vigencia_fim.is_(None), RegraEncargoModel.vigencia_fim >= competencia),
            )
            .order_by(RegraEncargoModel.prioridade.asc(), RegraEncargoModel.codigo.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[RegraEncargo]:
        stmt = self._build_filters(select(RegraEncargoModel), team_id)
        stmt = stmt.order_by(RegraEncargoModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[RegraEncargo]:
        stmt = self._build_filters(select(RegraEncargoModel), team_id, **filters)
        stmt = stmt.order_by(RegraEncargoModel.created_at.desc()).limit(limit).offset((page - 1) * limit)
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        stmt = self._build_filters(select(func.count()).select_from(RegraEncargoModel), team_id, load_relationships=False, **filters)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def has_active_conflict(
        self,
        team_id: UUID,
        regra_grupo_id: UUID,
        codigo: str,
        vigencia_inicio,
        vigencia_fim,
        aplicabilidades: list,
        exclude_id: UUID | None = None,
    ) -> bool:
        open_end = datetime.max.replace(tzinfo=getattr(vigencia_inicio, "tzinfo", None))
        stmt = (
            select(RegraEncargoModel)
            .options(selectinload(RegraEncargoModel.aplicabilidades))
            .where(
                RegraEncargoModel.team_id == team_id,
                RegraEncargoModel.regra_grupo_id == regra_grupo_id,
                RegraEncargoModel.codigo == codigo,
                RegraEncargoModel.status == StatusRegraEncargo.ATIVA.value,
                RegraEncargoModel.is_deleted == False,  # noqa: E712
                RegraEncargoModel.vigencia_inicio <= (vigencia_fim or open_end),
                or_(RegraEncargoModel.vigencia_fim.is_(None), RegraEncargoModel.vigencia_fim >= vigencia_inicio),
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(RegraEncargoModel.id != exclude_id)
        result = await self._session.execute(stmt)
        requested = {(item.escopo.value if hasattr(item.escopo, "value") else str(item.escopo), item.valor) for item in aplicabilidades}
        for model in result.scalars().all():
            existing = {(item.escopo, item.valor) for item in model.aplicabilidades}
            if existing == requested:
                return True
        return False

    def _build_filters(self, stmt, team_id: UUID, load_relationships: bool = True, **filters):
        if load_relationships:
            stmt = stmt.options(
                selectinload(RegraEncargoModel.aplicabilidades),
                selectinload(RegraEncargoModel.tabela_progressiva).selectinload(TabelaProgressivaModel.faixas),
            )
        stmt = stmt.where(
            RegraEncargoModel.team_id == team_id,
            RegraEncargoModel.is_deleted == False,  # noqa: E712
        )
        if filters.get("search"):
            pattern = f"%{filters['search'].strip()}%"
            stmt = stmt.where(or_(RegraEncargoModel.codigo.ilike(pattern), RegraEncargoModel.nome.ilike(pattern)))
        for field in ("codigo", "status", "tipo_calculo", "natureza", "base_calculo"):
            if filters.get(field) is not None:
                value = filters[field]
                stmt = stmt.where(getattr(RegraEncargoModel, field) == (value.value if hasattr(value, "value") else str(value)))
        return stmt

    async def save(self, regra: RegraEncargo) -> RegraEncargo:
        stmt = (
            select(RegraEncargoModel)
            .options(
                selectinload(RegraEncargoModel.aplicabilidades),
                selectinload(RegraEncargoModel.tabela_progressiva).selectinload(TabelaProgressivaModel.faixas),
            )
            .where(RegraEncargoModel.id == regra.id, RegraEncargoModel.team_id == regra.team_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = RegraEncargoModel(
                id=regra.id,
                regra_grupo_id=regra.regra_grupo_id,
                team_id=regra.team_id,
                codigo=regra.codigo,
                nome=regra.nome,
                descricao=regra.descricao,
                tipo_calculo=regra.tipo_calculo.value,
                natureza=regra.natureza.value,
                base_calculo=regra.base_calculo.value,
                prioridade=regra.prioridade,
                vigencia_inicio=regra.vigencia_inicio,
                vigencia_fim=regra.vigencia_fim,
                status=regra.status.value,
                valor_fixo_amount=regra.valor_fixo.amount if regra.valor_fixo else None,
                valor_fixo_currency=regra.valor_fixo.currency if regra.valor_fixo else None,
                percentual=regra.percentual,
                tabela_progressiva_id=regra.tabela_progressiva_id,
                teto_amount=regra.teto.amount if regra.teto else None,
                teto_currency=regra.teto.currency if regra.teto else None,
                piso_amount=regra.piso.amount if regra.piso else None,
                piso_currency=regra.piso.currency if regra.piso else None,
                arredondamento=regra.arredondamento,
                incide_no_liquido=regra.incide_no_liquido,
                is_system=regra.is_system,
                created_by_user_id=regra.created_by_user_id,
                updated_by_user_id=regra.updated_by_user_id,
                approved_by_user_id=regra.approved_by_user_id,
                is_deleted=regra.is_deleted,
            )
            self._session.add(model)
            await self._session.flush()
        else:
            model.regra_grupo_id = regra.regra_grupo_id
            model.codigo = regra.codigo
            model.nome = regra.nome
            model.descricao = regra.descricao
            model.tipo_calculo = regra.tipo_calculo.value
            model.natureza = regra.natureza.value
            model.base_calculo = regra.base_calculo.value
            model.prioridade = regra.prioridade
            model.vigencia_inicio = regra.vigencia_inicio
            model.vigencia_fim = regra.vigencia_fim
            model.status = regra.status.value
            model.valor_fixo_amount = regra.valor_fixo.amount if regra.valor_fixo else None
            model.valor_fixo_currency = regra.valor_fixo.currency if regra.valor_fixo else None
            model.percentual = regra.percentual
            model.tabela_progressiva_id = regra.tabela_progressiva_id
            model.teto_amount = regra.teto.amount if regra.teto else None
            model.teto_currency = regra.teto.currency if regra.teto else None
            model.piso_amount = regra.piso.amount if regra.piso else None
            model.piso_currency = regra.piso.currency if regra.piso else None
            model.arredondamento = regra.arredondamento
            model.incide_no_liquido = regra.incide_no_liquido
            model.is_system = regra.is_system
            model.created_by_user_id = regra.created_by_user_id
            model.updated_by_user_id = regra.updated_by_user_id
            model.approved_by_user_id = regra.approved_by_user_id
            model.is_deleted = regra.is_deleted
            for aplic_model in list(model.aplicabilidades):
                await self._session.delete(aplic_model)
            await self._session.flush()

        for aplicabilidade in regra.aplicabilidades:
            self._session.add(
                RegraEncargoAplicabilidadeModel(
                    id=aplicabilidade.id,
                    team_id=aplicabilidade.team_id,
                    regra_encargo_id=model.id,
                    escopo=aplicabilidade.escopo.value,
                    valor=aplicabilidade.valor,
                )
            )
        await self._session.flush()
        return await self.get_by_id(model.id, regra.team_id)


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


class HoleriteItemRepositoryImpl(HoleriteItemRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_holerite(self, team_id: UUID, holerite_id: UUID) -> list[HoleriteItem]:
        stmt = (
            select(HoleriteItemModel)
            .where(
                HoleriteItemModel.team_id == team_id,
                HoleriteItemModel.holerite_id == holerite_id,
            )
            .order_by(HoleriteItemModel.ordem.asc(), HoleriteItemModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def replace_automaticos(self, team_id: UUID, holerite_id: UUID, items: list[HoleriteItem]) -> list[HoleriteItem]:
        stmt = select(HoleriteItemModel).where(
            HoleriteItemModel.team_id == team_id,
            HoleriteItemModel.holerite_id == holerite_id,
            HoleriteItemModel.is_automatico == True,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._session.delete(model)
        await self._session.flush()
        for item in items:
            self._session.add(HoleriteItemModel.from_domain(item))
        await self._session.flush()
        return await self.list_by_holerite(team_id, holerite_id)

    async def save(self, item: HoleriteItem) -> HoleriteItem:
        model = HoleriteItemModel.from_domain(item)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()


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


class RhFolhaJobRepositoryImpl(RhFolhaJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: RhFolhaJob) -> RhFolhaJob:
        stmt = select(RhFolhaJobModel).where(RhFolhaJobModel.id == job.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = RhFolhaJobModel.from_domain(job)
            self._session.add(model)
        else:
            model.update_from_domain(job)
        await self._session.flush()
        return model.to_domain()

    async def get_by_id(self, team_id: UUID, job_id: UUID) -> RhFolhaJob:
        stmt = select(RhFolhaJobModel).where(
            RhFolhaJobModel.id == job_id,
            RhFolhaJobModel.team_id == team_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise DomainError("Job de folha nao encontrado")
        return model.to_domain()

    async def get_by_id_unscoped(self, job_id: UUID) -> RhFolhaJob:
        stmt = select(RhFolhaJobModel).where(RhFolhaJobModel.id == job_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise DomainError("Job de folha nao encontrado")
        return model.to_domain()

    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[RhFolhaJob]:
        stmt = (
            select(RhFolhaJobModel)
            .where(RhFolhaJobModel.team_id == team_id)
            .order_by(RhFolhaJobModel.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        result = await self._session.execute(stmt)
        return [model.to_domain() for model in result.scalars().all()]

    async def count_by_team(self, team_id: UUID) -> int:
        stmt = select(func.count()).select_from(RhFolhaJobModel).where(RhFolhaJobModel.team_id == team_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())


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
