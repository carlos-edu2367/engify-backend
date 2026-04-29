from abc import ABC, abstractmethod
from uuid import UUID

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
    TipoAtestado,
)


class FuncionarioRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> Funcionario:
        pass

    @abstractmethod
    async def get_by_cpf(self, team_id: UUID, cpf: str) -> Funcionario | None:
        pass

    @abstractmethod
    async def get_by_user_id(self, team_id: UUID, user_id: UUID) -> Funcionario | None:
        pass

    @abstractmethod
    async def list_by_team(
        self,
        team_id: UUID,
        page: int,
        limit: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> list[Funcionario]:
        pass

    @abstractmethod
    async def count_by_team(
        self,
        team_id: UUID,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        pass

    @abstractmethod
    async def list_active_by_team(self, team_id: UUID, limit: int, offset: int) -> list[Funcionario]:
        pass

    @abstractmethod
    async def save(self, funcionario: Funcionario) -> Funcionario:
        pass


class RhSalarioHistoricoRepository(ABC):
    @abstractmethod
    async def save(self, historico: RhSalarioHistorico) -> RhSalarioHistorico:
        pass


class HorarioTrabalhoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> HorarioTrabalho:
        pass

    @abstractmethod
    async def get_by_funcionario_id(self, team_id: UUID, funcionario_id: UUID) -> HorarioTrabalho | None:
        pass

    @abstractmethod
    async def list_by_funcionarios(self, team_id: UUID, funcionario_ids: list[UUID]) -> dict[UUID, HorarioTrabalho]:
        pass

    @abstractmethod
    async def save(self, horario: HorarioTrabalho) -> HorarioTrabalho:
        pass


class FeriasRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> Ferias:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Ferias]:
        pass

    @abstractmethod
    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[Ferias]:
        pass

    @abstractmethod
    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        pass

    @abstractmethod
    async def has_overlap(self, team_id: UUID, funcionario_id: UUID, start, end, statuses, exclude_id: UUID | None = None) -> bool:
        pass

    @abstractmethod
    async def list_by_competencia(self, team_id: UUID, funcionario_ids: list[UUID], start, end, statuses) -> list[Ferias]:
        pass

    @abstractmethod
    async def save(self, ferias: Ferias) -> Ferias:
        pass


class LocalPontoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> LocalPonto:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[LocalPonto]:
        pass

    @abstractmethod
    async def list_by_funcionario(self, team_id: UUID, funcionario_id: UUID) -> list[LocalPonto]:
        pass

    @abstractmethod
    async def save(self, local_ponto: LocalPonto) -> LocalPonto:
        pass


class RegistroPontoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> RegistroPonto:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[RegistroPonto]:
        pass

    @abstractmethod
    async def count_by_team(self, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def list_by_team_periodo(
        self,
        team_id: UUID,
        start,
        end,
        status=None,
        page: int = 1,
        limit: int = 50,
    ) -> list[RegistroPonto]:
        pass

    @abstractmethod
    async def list_by_funcionario_periodo(
        self,
        team_id: UUID,
        funcionario_id: UUID,
        start,
        end,
        status=None,
        page: int = 1,
        limit: int = 50,
    ) -> list[RegistroPonto]:
        pass

    @abstractmethod
    async def count_by_funcionario_periodo(self, team_id: UUID, funcionario_id: UUID, start, end, status=None) -> int:
        pass

    @abstractmethod
    async def count_by_team_periodo(self, team_id: UUID, start, end, status=None) -> int:
        pass

    @abstractmethod
    async def get_last_valid_by_funcionario(self, team_id: UUID, funcionario_id: UUID) -> RegistroPonto | None:
        pass

    @abstractmethod
    async def get_last_valid_on_day(self, team_id: UUID, funcionario_id: UUID, day_start, day_end) -> RegistroPonto | None:
        pass

    @abstractmethod
    async def list_by_funcionario_day(self, team_id: UUID, funcionario_id: UUID, day_start, day_end) -> list[RegistroPonto]:
        pass

    @abstractmethod
    async def list_by_competencia(self, team_id: UUID, funcionario_ids: list[UUID], start, end) -> list[RegistroPonto]:
        pass

    @abstractmethod
    async def save(self, registro: RegistroPonto) -> RegistroPonto:
        pass


class AjustePontoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> AjustePonto:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[AjustePonto]:
        pass

    @abstractmethod
    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[AjustePonto]:
        pass

    @abstractmethod
    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        pass

    @abstractmethod
    async def has_pending_duplicate(self, team_id: UUID, funcionario_id: UUID, data_referencia, entrada, saida) -> bool:
        pass

    @abstractmethod
    async def save(self, ajuste: AjustePonto) -> AjustePonto:
        pass


class TipoAtestadoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> TipoAtestado:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[TipoAtestado]:
        pass

    @abstractmethod
    async def list_active(self, team_id: UUID, page: int, limit: int) -> list[TipoAtestado]:
        pass

    @abstractmethod
    async def count_active(self, team_id: UUID) -> int:
        pass

    @abstractmethod
    async def save(self, tipo_atestado: TipoAtestado) -> TipoAtestado:
        pass


class AtestadoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> Atestado:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Atestado]:
        pass

    @abstractmethod
    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[Atestado]:
        pass

    @abstractmethod
    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        pass

    @abstractmethod
    async def list_due_for_expiration(self, now, limit: int = 500, team_id: UUID | None = None) -> list[Atestado]:
        pass

    @abstractmethod
    async def list_by_competencia(self, team_id: UUID, funcionario_ids: list[UUID], start, end, statuses) -> list[Atestado]:
        pass

    @abstractmethod
    async def save(self, atestado: Atestado) -> Atestado:
        pass


class HoleriteRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID, team_id: UUID) -> Holerite:
        pass

    @abstractmethod
    async def list_by_team(self, team_id: UUID, page: int, limit: int) -> list[Holerite]:
        pass

    @abstractmethod
    async def get_by_competencia(self, team_id: UUID, funcionario_id: UUID, mes: int, ano: int) -> Holerite | None:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def count_by_competencia(self, team_id: UUID, mes: int, ano: int, status=None, funcionario_id: UUID | None = None) -> int:
        pass

    @abstractmethod
    async def list_rascunhos_by_competencia(
        self,
        team_id: UUID,
        mes: int,
        ano: int,
        limit: int = 500,
        funcionario_ids: list[UUID] | None = None,
    ) -> list[Holerite]:
        pass

    @abstractmethod
    async def list_by_funcionario(self, team_id: UUID, funcionario_id: UUID, page: int, limit: int) -> list[Holerite]:
        pass

    @abstractmethod
    async def count_by_funcionario(self, team_id: UUID, funcionario_id: UUID) -> int:
        pass

    @abstractmethod
    async def summarize_by_competencia(self, team_id: UUID, mes: int, ano: int) -> dict:
        pass

    @abstractmethod
    async def save(self, holerite: Holerite) -> Holerite:
        pass


class RhAuditLogRepository(ABC):
    @abstractmethod
    async def save(self, audit_log: RhAuditLog) -> RhAuditLog:
        pass

    @abstractmethod
    async def list_by_filters(self, team_id: UUID, page: int, limit: int, **filters) -> list[RhAuditLog]:
        pass

    @abstractmethod
    async def count_by_filters(self, team_id: UUID, **filters) -> int:
        pass


class RhIdempotencyKeyRepository(ABC):
    @abstractmethod
    async def get_by_key(self, team_id: UUID, scope: str, key: str) -> RhIdempotencyKey | None:
        pass

    @abstractmethod
    async def exists_or_create(self, team_id: UUID, scope: str, key: str) -> bool:
        pass
