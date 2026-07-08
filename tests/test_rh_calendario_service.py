from datetime import date, datetime, time, timezone
from uuid import uuid4

import pytest

from app.application.dtos.rh import CreateEventoCalendarioDTO
from app.domain.entities.identities import CPF
from app.domain.entities.rh_calendario import EventoCalendarioRh, TipoEventoCalendario
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


def _make_user(role: Roles, team_id=None) -> User:
    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Carlos"
    user.email = "carlos@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = _make_team(team_id)
    user.cpf = CPF("52998224725")
    return user


class _FakeEventoRepo:
    def __init__(self, items=None) -> None:
        self.items = list(items or [])

    async def save(self, evento):
        self.items = [item for item in self.items if item.id != evento.id]
        self.items.append(evento)
        return evento

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Evento de calendario nao encontrado")

    async def list_by_periodo(self, team_id, start, end):
        return [
            item
            for item in self.items
            if item.team_id == team_id and start <= item.data <= end and not item.is_deleted
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


def _build_service(items=None):
    from app.application.services.rh_calendario_service import RhCalendarioService

    return RhCalendarioService(
        evento_repo=_FakeEventoRepo(items),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
    )


@pytest.mark.asyncio
async def test_criar_evento_denies_role_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    service = _build_service()

    with pytest.raises(DomainError):
        await service.criar_evento(
            CreateEventoCalendarioDTO(tipo="feriado", data=date(2026, 12, 25), descricao="Natal"),
            employee,
        )


@pytest.mark.asyncio
async def test_criar_evento_persiste_e_audita():
    admin = _make_user(Roles.ADMIN)
    service = _build_service()

    evento = await service.criar_evento(
        CreateEventoCalendarioDTO(tipo="feriado", data=date(2026, 12, 25), descricao="Natal"),
        admin,
    )

    assert evento.tipo == TipoEventoCalendario.FERIADO
    assert evento.aplica_todos is True
    assert service.audit_repo.events[-1].action == "rh.calendario.evento_criado"
    assert service.uow.commits == 1


@pytest.mark.asyncio
async def test_criar_evento_liberacao_antecipada_exige_hora_corte():
    admin = _make_user(Roles.ADMIN)
    service = _build_service()

    with pytest.raises(DomainError):
        await service.criar_evento(
            CreateEventoCalendarioDTO(tipo="liberacao_antecipada", data=date(2026, 12, 24), descricao="Vespera"),
            admin,
        )


@pytest.mark.asyncio
async def test_list_eventos_filtra_por_periodo():
    admin = _make_user(Roles.ADMIN)
    dentro = EventoCalendarioRh(
        team_id=admin.team.id, tipo=TipoEventoCalendario.FERIADO, data=date(2026, 12, 25), descricao="Natal"
    )
    fora = EventoCalendarioRh(
        team_id=admin.team.id, tipo=TipoEventoCalendario.FERIADO, data=date(2026, 1, 1), descricao="Ano novo"
    )
    service = _build_service([dentro, fora])

    result = await service.list_eventos(admin, date(2026, 12, 1), date(2026, 12, 31))

    assert [item.id for item in result] == [dentro.id]


@pytest.mark.asyncio
async def test_remover_evento_soft_deletes_e_audita():
    admin = _make_user(Roles.ADMIN)
    evento = EventoCalendarioRh(
        team_id=admin.team.id, tipo=TipoEventoCalendario.FERIADO, data=date(2026, 12, 25), descricao="Natal"
    )
    service = _build_service([evento])

    await service.remover_evento(evento.id, admin)

    persisted = next(item for item in service.evento_repo.items if item.id == evento.id)
    assert persisted.is_deleted is True
    assert service.audit_repo.events[-1].action == "rh.calendario.evento_removido"


@pytest.mark.asyncio
async def test_list_eventos_denies_role_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    service = _build_service()

    with pytest.raises(DomainError):
        await service.list_eventos(employee, date(2026, 1, 1), date(2026, 12, 31))
