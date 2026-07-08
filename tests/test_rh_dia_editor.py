from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dtos.rh import BatidaDiaDTO, EditarDiaPontoDTO
from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Funcionario,
    Holerite,
    RegistroPonto,
    RhAuditLog,
    StatusHolerite,
    StatusPonto,
    TipoPonto,
)
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


def _make_funcionario(team_id) -> Funcionario:
    return Funcionario(
        team_id=team_id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("2200.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )


class _FakeFuncionarioRepo:
    def __init__(self, funcionarios) -> None:
        self.by_id = {item.id: item for item in funcionarios}

    async def get_by_id(self, id, team_id):
        item = self.by_id.get(id)
        if not item or item.team_id != team_id or item.is_deleted:
            raise DomainError("Funcionario nao encontrado")
        return item

    async def get_by_user_id(self, team_id, user_id):
        return None


class _FakeLocalPontoRepo:
    async def list_by_funcionario(self, team_id, funcionario_id):
        return []


class _FakeRegistroPontoRepo:
    def __init__(self, registros=None) -> None:
        self.items = list(registros or [])

    async def list_by_funcionario_day(self, team_id, funcionario_id, day_start, day_end):
        return [
            item
            for item in self.items
            if item.team_id == team_id
            and item.funcionario_id == funcionario_id
            and day_start <= item.timestamp <= day_end
            and not item.is_deleted
        ]

    async def save(self, registro):
        for idx, item in enumerate(self.items):
            if item.id == registro.id:
                self.items[idx] = registro
                return registro
        self.items.append(registro)
        return registro


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log

    async def list_by_filters(self, team_id, page, limit, **filters):
        return []


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _FakeGeofenceCache:
    async def get_locais(self, team_id, funcionario_id):
        return []

    async def set_locais(self, team_id, funcionario_id, locais):
        return None

    async def invalidate(self, team_id, funcionario_id):
        return None


class _FakeHoleriteCompetenciaRepo:
    def __init__(self, holerite=None) -> None:
        self._holerite = holerite

    async def get_by_competencia(self, team_id, funcionario_id, mes, ano):
        return self._holerite


def _build_service(funcionario, registros=None, holerite=None, folha_recalc=None):
    from app.application.services.rh_ponto_service import RhPontoService

    return RhPontoService(
        funcionario_repo=_FakeFuncionarioRepo([funcionario]),
        local_ponto_repo=_FakeLocalPontoRepo(),
        registro_ponto_repo=_FakeRegistroPontoRepo(registros),
        audit_repo=_FakeAuditRepo(),
        geofence_cache=_FakeGeofenceCache(),
        idempotency_repo=None,
        uow=_FakeUow(),
        holerite_repo=_FakeHoleriteCompetenciaRepo(holerite),
        folha_recalc=folha_recalc,
    )


@pytest.mark.asyncio
async def test_editar_dia_ponto_cria_batidas_em_dia_vazio():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    service = _build_service(funcionario)

    dto = EditarDiaPontoDTO(
        funcionario_id=funcionario.id,
        data=date(2026, 4, 28),
        batidas=[
            BatidaDiaDTO(tipo=TipoPonto.ENTRADA, hora=time(8, 0)),
            BatidaDiaDTO(tipo=TipoPonto.SAIDA, hora=time(17, 0)),
        ],
        motivo="Funcionario esqueceu de bater o ponto",
    )

    detail = await service.editar_dia_ponto(dto, admin)

    registros = detail["registros"]
    assert len(registros) == 2
    assert all(item.status == StatusPonto.AJUSTADO for item in registros)
    assert {item.tipo for item in registros} == {TipoPonto.ENTRADA, TipoPonto.SAIDA}


@pytest.mark.asyncio
async def test_editar_dia_ponto_substitui_batidas_existentes():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    existente = RegistroPonto(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        tipo=TipoPonto.ENTRADA,
        timestamp=datetime(2026, 4, 28, 8, 30, tzinfo=timezone.utc),
        latitude=-16.68,
        longitude=-49.26,
    )
    registro_repo = _FakeRegistroPontoRepo([existente])
    service = _build_service(funcionario)
    service.registro_ponto_repo = registro_repo

    dto = EditarDiaPontoDTO(
        funcionario_id=funcionario.id,
        data=date(2026, 4, 28),
        batidas=[
            BatidaDiaDTO(tipo=TipoPonto.ENTRADA, hora=time(8, 0)),
            BatidaDiaDTO(tipo=TipoPonto.SAIDA, hora=time(17, 0)),
        ],
        motivo="Corrigir horario de entrada",
    )

    await service.editar_dia_ponto(dto, admin)

    assert registro_repo.items[0].is_deleted is True
    ativos = [item for item in registro_repo.items if not item.is_deleted]
    assert len(ativos) == 2
    assert all(item.latitude == -16.68 and item.longitude == -49.26 for item in ativos)


@pytest.mark.asyncio
async def test_editar_dia_ponto_recusa_competencia_fechada():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    holerite_fechado = Holerite(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        mes_referencia=4,
        ano_referencia=2026,
        salario_base=Money(Decimal("2200.00")),
        horas_extras=Money(Decimal("0.00")),
        descontos_falta=Money(Decimal("0.00")),
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        valor_liquido=Money(Decimal("2200.00")),
        status=StatusHolerite.FECHADO,
    )
    service = _build_service(funcionario, holerite=holerite_fechado)

    dto = EditarDiaPontoDTO(
        funcionario_id=funcionario.id,
        data=date(2026, 4, 28),
        batidas=[BatidaDiaDTO(tipo=TipoPonto.ENTRADA, hora=time(8, 0))],
        motivo="Tentativa em competencia fechada",
    )

    with pytest.raises(DomainError):
        await service.editar_dia_ponto(dto, admin)


@pytest.mark.asyncio
async def test_editar_dia_ponto_denies_role_funcionario():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id)
    service = _build_service(funcionario)

    dto = EditarDiaPontoDTO(
        funcionario_id=funcionario.id,
        data=date(2026, 4, 28),
        batidas=[BatidaDiaDTO(tipo=TipoPonto.ENTRADA, hora=time(8, 0))],
        motivo="Tentativa nao autorizada",
    )

    with pytest.raises(DomainError):
        await service.editar_dia_ponto(dto, employee)


@pytest.mark.asyncio
async def test_editar_dia_ponto_recalcula_folha_quando_ha_rascunho():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    holerite_rascunho = Holerite(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        mes_referencia=4,
        ano_referencia=2026,
        salario_base=Money(Decimal("2200.00")),
        horas_extras=Money(Decimal("0.00")),
        descontos_falta=Money(Decimal("0.00")),
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        valor_liquido=Money(Decimal("2200.00")),
        status=StatusHolerite.RASCUNHO,
    )
    calls = []

    async def _recalc(current_user, mes, ano, funcionario_id):
        calls.append((mes, ano, funcionario_id))

    service = _build_service(funcionario, holerite=holerite_rascunho, folha_recalc=_recalc)

    dto = EditarDiaPontoDTO(
        funcionario_id=funcionario.id,
        data=date(2026, 4, 28),
        batidas=[BatidaDiaDTO(tipo=TipoPonto.ENTRADA, hora=time(8, 0))],
        motivo="Corrige jornada",
    )

    await service.editar_dia_ponto(dto, admin)

    assert calls == [(4, 2026, funcionario.id)]
