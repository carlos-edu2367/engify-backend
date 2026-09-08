from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dtos.rh import AbonarFaltaItemDTO, AbonarFaltasDTO
from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Atestado,
    Funcionario,
    HorarioTrabalho,
    StatusAtestado,
    TipoAtestado,
    TurnoHorario,
)
from app.domain.entities.rh_abono import AbonoFalta
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


def _make_funcionario(team_id, user_id=None) -> Funcionario:
    return Funcionario(
        team_id=team_id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("2200.00")),
        data_admissao=datetime(2026, 1, 1, tzinfo=timezone.utc),
        user_id=user_id,
    )


def _make_horario(team_id, funcionario_id) -> HorarioTrabalho:
    return HorarioTrabalho(
        team_id=team_id,
        funcionario_id=funcionario_id,
        turnos=[
            TurnoHorario(dia_semana=weekday, hora_entrada=time(8, 0), hora_saida=time(17, 0))
            for weekday in range(0, 5)
        ],
    )


class _FakeFuncionarioRepo:
    def __init__(self, funcionarios=None) -> None:
        self.funcionarios = list(funcionarios or [])

    async def get_by_id(self, id, team_id):
        for item in self.funcionarios:
            if item.id == id and item.team_id == team_id:
                return item
        raise DomainError("Funcionario nao encontrado")

    async def get_by_user_id(self, team_id, user_id):
        for item in self.funcionarios:
            if item.team_id == team_id and item.user_id == user_id:
                return item
        return None

    async def list_active_by_team(self, team_id, limit, offset):
        if offset > 0:
            return []
        return [item for item in self.funcionarios if item.team_id == team_id and item.is_active]


class _FakeHorarioRepo:
    def __init__(self, horarios=None) -> None:
        self.horarios = dict(horarios or {})

    async def list_by_funcionarios(self, team_id, funcionario_ids):
        return {fid: self.horarios[fid] for fid in funcionario_ids if fid in self.horarios}


class _FakeRegistroRepo:
    def __init__(self, registros=None) -> None:
        self.registros = list(registros or [])

    async def list_by_competencia(self, team_id, funcionario_ids, start, end):
        return [
            item
            for item in self.registros
            if item.funcionario_id in funcionario_ids and start <= item.timestamp <= end
        ]


class _FakeFeriasRepo:
    async def list_by_competencia(self, team_id, funcionario_ids, start, end, statuses):
        return []


class _FakeAtestadoRepo:
    def __init__(self, atestados=None) -> None:
        self.atestados = list(atestados or [])

    async def list_by_competencia(self, team_id, funcionario_ids, start, end, statuses):
        return [
            item
            for item in self.atestados
            if item.funcionario_id in funcionario_ids and item.status in statuses
        ]


class _FakeTipoAtestadoRepo:
    def __init__(self, tipos=None) -> None:
        self.tipos = dict(tipos or {})

    async def get_by_id(self, id, team_id):
        return self.tipos[id]


class _FakeEventoCalendarioRepo:
    async def list_by_periodo(self, team_id, start, end):
        return []


class _FakeAbonoRepo:
    def __init__(self, items=None) -> None:
        self.items = list(items or [])

    async def save(self, abono):
        self.items = [item for item in self.items if item.id != abono.id]
        self.items.append(abono)
        return abono

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Abono nao encontrado")

    async def list_by_periodo(self, team_id, start, end, funcionario_id=None):
        return [
            item
            for item in self.items
            if item.team_id == team_id
            and start <= item.data <= end
            and not item.is_deleted
            and (funcionario_id is None or item.funcionario_id == funcionario_id)
        ]

    async def list_by_funcionario_periodo(self, team_id, funcionario_id, start, end):
        return [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and start <= item.data <= end
            and not item.is_deleted
        ]


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1


def _build_service(
    funcionarios=None,
    horarios=None,
    registros=None,
    atestados=None,
    tipos_atestado=None,
    abonos=None,
):
    from app.application.services.rh_abono_service import RhAbonoService

    return RhAbonoService(
        funcionario_repo=_FakeFuncionarioRepo(funcionarios),
        horario_repo=_FakeHorarioRepo(horarios),
        registro_ponto_repo=_FakeRegistroRepo(registros),
        ferias_repo=_FakeFeriasRepo(),
        atestado_repo=_FakeAtestadoRepo(atestados),
        tipo_atestado_repo=_FakeTipoAtestadoRepo(tipos_atestado),
        abono_repo=_FakeAbonoRepo(abonos),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
        evento_calendario_repo=_FakeEventoCalendarioRepo(),
    )


@pytest.mark.asyncio
async def test_abonar_denies_role_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id)
    service = _build_service(funcionarios=[funcionario])

    with pytest.raises(DomainError):
        await service.abonar(
            AbonarFaltasDTO(itens=[AbonarFaltaItemDTO(funcionario_id=funcionario.id, data=date(2026, 3, 12))], motivo="Atestado"),
            employee,
        )


@pytest.mark.asyncio
async def test_abonar_cria_e_audita_por_item_e_comita_uma_vez():
    admin = _make_user(Roles.ADMIN)
    f1 = _make_funcionario(admin.team.id)
    f2 = _make_funcionario(admin.team.id)
    service = _build_service(funcionarios=[f1, f2])

    criados = await service.abonar(
        AbonarFaltasDTO(
            itens=[
                AbonarFaltaItemDTO(funcionario_id=f1.id, data=date(2026, 3, 12)),
                AbonarFaltaItemDTO(funcionario_id=f2.id, data=date(2026, 3, 12)),
            ],
            motivo="Atestado entregue fora do prazo",
        ),
        admin,
    )

    assert len(criados) == 2
    assert {item.funcionario_id for item in criados} == {f1.id, f2.id}
    assert all(item.motivo == "Atestado entregue fora do prazo" for item in criados)
    assert len([e for e in service.audit_repo.events if e.action == "rh.abono.criado"]) == 2
    assert service.uow.commits == 1


@pytest.mark.asyncio
async def test_abonar_ignora_data_ja_abonada_para_o_mesmo_funcionario():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    existente = AbonoFalta(team_id=admin.team.id, funcionario_id=funcionario.id, data=date(2026, 3, 12), motivo="Ja abonado")
    service = _build_service(funcionarios=[funcionario], abonos=[existente])

    criados = await service.abonar(
        AbonarFaltasDTO(itens=[AbonarFaltaItemDTO(funcionario_id=funcionario.id, data=date(2026, 3, 12))], motivo="Novo motivo"),
        admin,
    )

    assert criados == []
    assert service.uow.commits == 0


@pytest.mark.asyncio
async def test_listar_abonos_filtra_por_periodo_e_nega_role_funcionario():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    dentro = AbonoFalta(team_id=admin.team.id, funcionario_id=funcionario.id, data=date(2026, 3, 12), motivo="Atestado")
    fora = AbonoFalta(team_id=admin.team.id, funcionario_id=funcionario.id, data=date(2026, 1, 1), motivo="Atestado")
    service = _build_service(funcionarios=[funcionario], abonos=[dentro, fora])

    result = await service.listar_abonos(admin, date(2026, 3, 1), date(2026, 3, 31))

    assert [item.id for item in result] == [dentro.id]

    employee = _make_user(Roles.FUNCIONARIO, team_id=admin.team.id)
    with pytest.raises(DomainError):
        await service.listar_abonos(employee, date(2026, 3, 1), date(2026, 3, 31))


@pytest.mark.asyncio
async def test_revogar_soft_deletes_e_audita():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    abono = AbonoFalta(team_id=admin.team.id, funcionario_id=funcionario.id, data=date(2026, 3, 12), motivo="Atestado")
    service = _build_service(funcionarios=[funcionario], abonos=[abono])

    revogado = await service.revogar(abono.id, admin)

    assert revogado.is_deleted is True
    assert service.audit_repo.events[-1].action == "rh.abono.revogado"
    assert service.uow.commits == 1


@pytest.mark.asyncio
async def test_revogar_denies_role_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    abono = AbonoFalta(team_id=employee.team.id, funcionario_id=uuid4(), data=date(2026, 3, 12), motivo="Atestado")
    service = _build_service(abonos=[abono])

    with pytest.raises(DomainError):
        await service.revogar(abono.id, employee)


@pytest.mark.asyncio
async def test_listar_meus_abonos_filtra_por_funcionario_vinculado_e_periodo():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id, user_id=employee.id)
    dentro = AbonoFalta(team_id=employee.team.id, funcionario_id=funcionario.id, data=date(2026, 3, 12), motivo="Atestado")
    fora = AbonoFalta(team_id=employee.team.id, funcionario_id=funcionario.id, data=date(2026, 1, 1), motivo="Atestado")
    service = _build_service(funcionarios=[funcionario], abonos=[dentro, fora])

    result = await service.listar_meus_abonos(employee, date(2026, 3, 1), date(2026, 3, 31))

    assert [item.id for item in result] == [dentro.id]


@pytest.mark.asyncio
async def test_listar_meus_abonos_sem_funcionario_vinculado_retorna_vazio():
    employee = _make_user(Roles.FUNCIONARIO)
    service = _build_service()

    result = await service.listar_meus_abonos(employee, date(2026, 3, 1), date(2026, 3, 31))

    assert result == []


@pytest.mark.asyncio
async def test_listar_faltas_denies_role_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    service = _build_service()

    with pytest.raises(DomainError):
        await service.listar_faltas(employee, date(2026, 3, 9), date(2026, 3, 9))


@pytest.mark.asyncio
async def test_listar_faltas_retorna_dia_sem_registro():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = _make_horario(admin.team.id, funcionario.id)
    service = _build_service(funcionarios=[funcionario], horarios={funcionario.id: horario})

    # 2026-03-09 e' segunda-feira, dia com turno e sem nenhuma batida.
    result = await service.listar_faltas(admin, date(2026, 3, 9), date(2026, 3, 9))

    assert len(result) == 1
    assert result[0].funcionario_id == funcionario.id
    assert result[0].data == date(2026, 3, 9)


@pytest.mark.asyncio
async def test_listar_faltas_nao_lista_dia_ja_abonado():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = _make_horario(admin.team.id, funcionario.id)
    abono = AbonoFalta(team_id=admin.team.id, funcionario_id=funcionario.id, data=date(2026, 3, 9), motivo="Ja abonado")
    service = _build_service(
        funcionarios=[funcionario],
        horarios={funcionario.id: horario},
        abonos=[abono],
    )

    result = await service.listar_faltas(admin, date(2026, 3, 9), date(2026, 3, 9))

    assert result == []


@pytest.mark.asyncio
async def test_listar_faltas_nao_lista_dia_coberto_por_atestado_que_abona():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = _make_horario(admin.team.id, funcionario.id)
    tipo = TipoAtestado(team_id=admin.team.id, nome="Medico", prazo_entrega_dias=2, abona_falta=True)
    atestado = Atestado(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        tipo_atestado_id=tipo.id,
        data_inicio=datetime(2026, 3, 9, tzinfo=timezone.utc),
        data_fim=datetime(2026, 3, 9, tzinfo=timezone.utc),
        status=StatusAtestado.ENTREGUE,
    )
    service = _build_service(
        funcionarios=[funcionario],
        horarios={funcionario.id: horario},
        atestados=[atestado],
        tipos_atestado={tipo.id: tipo},
    )

    result = await service.listar_faltas(admin, date(2026, 3, 9), date(2026, 3, 9))

    assert result == []
