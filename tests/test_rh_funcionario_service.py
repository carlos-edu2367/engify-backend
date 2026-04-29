from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import Funcionario, HorarioTrabalho, RhAuditLog, TurnoHorario
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError


def _make_team(team_id=None) -> Team:
    team = object.__new__(Team)
    team.id = team_id or uuid4()
    team.title = "Engify"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc)
    return team


def _make_user(role: Roles, team_id=None, user_id=None) -> User:
    user = object.__new__(User)
    user.id = user_id or uuid4()
    user.nome = "Carlos"
    user.email = "carlos@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = _make_team(team_id)
    user.cpf = CPF("52998224725")
    return user


class _FakeFuncionarioRepo:
    def __init__(self) -> None:
        self.by_id: dict = {}

    async def get_by_id(self, id, team_id):
        funcionario = self.by_id.get(id)
        if not funcionario or funcionario.team_id != team_id or funcionario.is_deleted:
            raise DomainError("Funcionario nao encontrado")
        return funcionario

    async def get_by_cpf(self, team_id, cpf):
        for funcionario in self.by_id.values():
            if funcionario.team_id == team_id and funcionario.cpf.value == cpf and not funcionario.is_deleted:
                return funcionario
        return None

    async def get_by_user_id(self, team_id, user_id):
        for funcionario in self.by_id.values():
            if funcionario.team_id == team_id and funcionario.user_id == user_id and not funcionario.is_deleted:
                return funcionario
        return None

    async def list_by_team(self, team_id, page, limit, search=None, is_active=None):
        items = [
            funcionario
            for funcionario in self.by_id.values()
            if funcionario.team_id == team_id and not funcionario.is_deleted
        ]
        if search:
            lowered = search.lower()
            items = [item for item in items if lowered in item.nome.lower() or lowered in item.cargo.lower()]
        if is_active is not None:
            items = [item for item in items if item.is_active is is_active]
        return sorted(items, key=lambda item: item.nome)[(page - 1) * limit : page * limit]

    async def count_by_team(self, team_id, search=None, is_active=None):
        items = await self.list_by_team(team_id, 1, 10_000, search=search, is_active=is_active)
        return len(items)

    async def list_active_by_team(self, team_id, limit, offset):
        items = [
            funcionario
            for funcionario in self.by_id.values()
            if funcionario.team_id == team_id and funcionario.is_active and not funcionario.is_deleted
        ]
        return sorted(items, key=lambda item: item.nome)[offset : offset + limit]

    async def save(self, funcionario):
        self.by_id[funcionario.id] = funcionario
        return funcionario


class _FakeHorarioRepo:
    def __init__(self) -> None:
        self.by_id: dict = {}
        self.by_funcionario_id: dict = {}

    async def get_by_id(self, id, team_id):
        horario = self.by_id.get(id)
        if not horario or horario.team_id != team_id or horario.is_deleted:
            raise DomainError("Horario nao encontrado")
        return horario

    async def get_by_funcionario_id(self, team_id, funcionario_id):
        horario = self.by_funcionario_id.get(funcionario_id)
        if not horario or horario.team_id != team_id or horario.is_deleted:
            return None
        return horario

    async def save(self, horario):
        self.by_id[horario.id] = horario
        self.by_funcionario_id[horario.funcionario_id] = horario
        return horario


class _FakeUserRepo:
    def __init__(self, users=None) -> None:
        self.by_id = {user.id: user for user in users or []}

    async def get_by_id(self, id):
        user = self.by_id.get(id)
        if not user:
            raise DomainError("Usuario nao encontrado")
        return user


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log


class _FakeSalarioHistoricoRepo:
    def __init__(self) -> None:
        self.items = []

    async def save(self, historico):
        self.items.append(historico)
        return historico


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_create_funcionario_creates_horario_and_audit_log():
    from app.application.dtos.rh import CreateFuncionarioDTO, TurnoHorarioDTO
    from app.application.services.rh_funcionario_service import RhFuncionarioService

    current_user = _make_user(Roles.ADMIN)
    funcionario_repo = _FakeFuncionarioRepo()
    horario_repo = _FakeHorarioRepo()
    audit_repo = _FakeAuditRepo()
    uow = _FakeUow()
    service = RhFuncionarioService(
        funcionario_repo=funcionario_repo,
        horario_repo=horario_repo,
        user_repo=_FakeUserRepo(),
        audit_repo=audit_repo,
        salario_historico_repo=_FakeSalarioHistoricoRepo(),
        uow=uow,
    )

    dto = CreateFuncionarioDTO(
        nome="Ana Souza",
        cpf="11144477735",
        cargo="Analista",
        salario_base=Decimal("4500.00"),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
        user_id=None,
        horario_trabalho=[
            TurnoHorarioDTO(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0)),
            TurnoHorarioDTO(dia_semana=1, hora_entrada=time(8, 0), hora_saida=time(17, 0)),
        ],
    )

    created = await service.create_funcionario(dto, current_user)

    assert created.nome == "Ana Souza"
    assert created.cpf.value == "11144477735"
    assert created.horario_trabalho is not None
    assert len(created.horario_trabalho.turnos) == 2
    assert audit_repo.events[-1].action == "rh.funcionario.created"
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_create_funcionario_rejects_duplicate_cpf_in_same_team():
    from app.application.dtos.rh import CreateFuncionarioDTO, TurnoHorarioDTO
    from app.application.services.rh_funcionario_service import RhFuncionarioService

    team_id = uuid4()
    current_user = _make_user(Roles.ADMIN, team_id=team_id)
    funcionario_repo = _FakeFuncionarioRepo()
    existing = Funcionario(
        team_id=team_id,
        nome="Existente",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("3000.00")),
        data_admissao=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await funcionario_repo.save(existing)

    service = RhFuncionarioService(
        funcionario_repo=funcionario_repo,
        horario_repo=_FakeHorarioRepo(),
        user_repo=_FakeUserRepo(),
        audit_repo=_FakeAuditRepo(),
        salario_historico_repo=_FakeSalarioHistoricoRepo(),
        uow=_FakeUow(),
    )

    dto = CreateFuncionarioDTO(
        nome="Ana Souza",
        cpf="11144477735",
        cargo="Analista",
        salario_base=Decimal("4500.00"),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
        user_id=None,
        horario_trabalho=[TurnoHorarioDTO(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )

    with pytest.raises(DomainError):
        await service.create_funcionario(dto, current_user)


@pytest.mark.asyncio
async def test_create_funcionario_rejects_user_from_other_team():
    from app.application.dtos.rh import CreateFuncionarioDTO, TurnoHorarioDTO
    from app.application.services.rh_funcionario_service import RhFuncionarioService

    current_user = _make_user(Roles.ADMIN)
    foreign_user = _make_user(Roles.FUNCIONARIO, team_id=uuid4())
    service = RhFuncionarioService(
        funcionario_repo=_FakeFuncionarioRepo(),
        horario_repo=_FakeHorarioRepo(),
        user_repo=_FakeUserRepo([foreign_user]),
        audit_repo=_FakeAuditRepo(),
        salario_historico_repo=_FakeSalarioHistoricoRepo(),
        uow=_FakeUow(),
    )

    dto = CreateFuncionarioDTO(
        nome="Ana Souza",
        cpf="11144477735",
        cargo="Analista",
        salario_base=Decimal("4500.00"),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
        user_id=foreign_user.id,
        horario_trabalho=[TurnoHorarioDTO(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )

    with pytest.raises(DomainError):
        await service.create_funcionario(dto, current_user)


@pytest.mark.asyncio
async def test_replace_horario_replaces_existing_turnos():
    from app.application.dtos.rh import ReplaceHorarioTrabalhoDTO, TurnoHorarioDTO
    from app.application.services.rh_funcionario_service import RhFuncionarioService

    current_user = _make_user(Roles.FINANCEIRO)
    funcionario = Funcionario(
        team_id=current_user.team.id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("4500.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    horario = HorarioTrabalho(
        team_id=current_user.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    funcionario_repo = _FakeFuncionarioRepo()
    horario_repo = _FakeHorarioRepo()
    await funcionario_repo.save(funcionario)
    await horario_repo.save(horario)

    service = RhFuncionarioService(
        funcionario_repo=funcionario_repo,
        horario_repo=horario_repo,
        user_repo=_FakeUserRepo(),
        audit_repo=_FakeAuditRepo(),
        salario_historico_repo=_FakeSalarioHistoricoRepo(),
        uow=_FakeUow(),
    )

    dto = ReplaceHorarioTrabalhoDTO(
        turnos=[
            TurnoHorarioDTO(dia_semana=2, hora_entrada=time(9, 0), hora_saida=time(18, 0)),
            TurnoHorarioDTO(dia_semana=3, hora_entrada=time(9, 0), hora_saida=time(18, 0)),
        ]
    )

    updated = await service.replace_horario(funcionario.id, dto, current_user)

    assert [turno.dia_semana for turno in updated.turnos] == [2, 3]
    assert horario_repo.by_funcionario_id[funcionario.id].turnos[0].hora_entrada == time(9, 0)


@pytest.mark.asyncio
async def test_delete_funcionario_soft_deletes_funcionario_and_horario():
    from app.application.services.rh_funcionario_service import RhFuncionarioService

    current_user = _make_user(Roles.ADMIN)
    funcionario = Funcionario(
        team_id=current_user.team.id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("4500.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    horario = HorarioTrabalho(
        team_id=current_user.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    funcionario_repo = _FakeFuncionarioRepo()
    horario_repo = _FakeHorarioRepo()
    await funcionario_repo.save(funcionario)
    await horario_repo.save(horario)

    service = RhFuncionarioService(
        funcionario_repo=funcionario_repo,
        horario_repo=horario_repo,
        user_repo=_FakeUserRepo(),
        audit_repo=_FakeAuditRepo(),
        salario_historico_repo=_FakeSalarioHistoricoRepo(),
        uow=_FakeUow(),
    )

    await service.delete_funcionario(funcionario.id, current_user)

    assert funcionario.is_deleted is True
    assert horario.is_deleted is True


@pytest.mark.asyncio
async def test_update_funcionario_salary_requires_reason_and_records_history():
    from app.application.dtos.rh import UpdateFuncionarioDTO
    from app.application.services.rh_funcionario_service import RhFuncionarioService

    current_user = _make_user(Roles.ADMIN)
    funcionario = Funcionario(
        team_id=current_user.team.id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("4500.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    funcionario_repo = _FakeFuncionarioRepo()
    await funcionario_repo.save(funcionario)
    salario_historico_repo = _FakeSalarioHistoricoRepo()
    service = RhFuncionarioService(
        funcionario_repo=funcionario_repo,
        horario_repo=_FakeHorarioRepo(),
        user_repo=_FakeUserRepo(),
        audit_repo=_FakeAuditRepo(),
        salario_historico_repo=salario_historico_repo,
        uow=_FakeUow(),
    )

    with pytest.raises(DomainError):
        await service.update_funcionario(
            funcionario.id,
            UpdateFuncionarioDTO(salario_base=Decimal("5000.00")),
            current_user,
        )

    updated = await service.update_funcionario(
        funcionario.id,
        UpdateFuncionarioDTO(salario_base=Decimal("5000.00")),
        current_user,
        reason="Promocao anual",
    )

    assert updated.salario_base.amount == Decimal("5000.00")
    assert len(salario_historico_repo.items) == 1
    assert salario_historico_repo.items[0].salario_anterior.amount == Decimal("4500.00")
    assert salario_historico_repo.items[0].salario_novo.amount == Decimal("5000.00")
