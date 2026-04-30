from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Holerite,
    RegistroPonto,
    RhAuditLog,
    StatusAjuste,
    StatusAtestado,
    StatusFerias,
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


class _FakeFuncionarioRepo:
    def __init__(self, funcionario=None) -> None:
        self.funcionario = funcionario

    async def get_by_user_id(self, team_id, user_id):
        if (
            self.funcionario
            and self.funcionario.team_id == team_id
            and self.funcionario.user_id == user_id
            and not self.funcionario.is_deleted
        ):
            return self.funcionario
        return None

    async def count_by_team(self, team_id, search=None, is_active=None):
        assert search is None
        assert is_active is True
        return 12


class _FakeAjusteRepo:
    async def count_by_filters(self, team_id, **filters):
        assert filters["status"] == StatusAjuste.PENDENTE
        if filters.get("funcionario_id") is not None:
            return 1
        return 3


class _FakeFeriasRepo:
    async def count_by_filters(self, team_id, **filters):
        status = filters["status"]
        if status == StatusFerias.EM_ANDAMENTO:
            return 1
        if status == StatusFerias.SOLICITADO:
            return 1
        raise AssertionError(f"unexpected status {status}")


class _FakeAtestadoRepo:
    async def count_by_filters(self, team_id, **filters):
        status = filters["status"]
        if status == StatusAtestado.AGUARDANDO_ENTREGA:
            if filters.get("funcionario_id") is not None:
                return 1
            return 2
        if status == StatusAtestado.VENCIDO:
            return 1
        raise AssertionError(f"unexpected status {status}")


class _FakeRegistroRepo:
    async def count_by_team_periodo(self, team_id, start, end, status):
        if status == StatusPonto.NEGADO:
            return 4
        if status == StatusPonto.INCONSISTENTE:
            return 2
        raise AssertionError(f"unexpected status {status}")

    async def list_by_funcionario_periodo(self, team_id, funcionario_id, start, end, status=None, page=1, limit=1):
        return [
            RegistroPonto(
                team_id=team_id,
                funcionario_id=funcionario_id,
                tipo=TipoPonto.ENTRADA,
                timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
                latitude=-16.6869,
                longitude=-49.2648,
                status=StatusPonto.VALIDADO,
            )
        ]


class _FakeHoleriteRepo:
    async def summarize_by_competencia(self, team_id, mes, ano):
        return {
            "rascunho": 5,
            "fechado": 7,
            "cancelado": 0,
            "total_liquido": Decimal("25400.00"),
        }

    async def list_by_funcionario(self, team_id, funcionario_id, page, limit):
        return [
            Holerite(
                team_id=team_id,
                funcionario_id=funcionario_id,
                mes_referencia=4,
                ano_referencia=2026,
                salario_base=Money(Decimal("4500.00")),
                horas_extras=Money(Decimal("120.00")),
                descontos_falta=Money(Decimal("0.00")),
                acrescimos_manuais=Money(Decimal("50.00")),
                descontos_manuais=Money(Decimal("25.00")),
                valor_liquido=Money(Decimal("4645.00")),
                status=StatusHolerite.FECHADO,
            )
        ]


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.saved_events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.saved_events.append(audit_log)
        return audit_log

    async def list_by_filters(self, team_id, page, limit, **filters):
        return [
            RhAuditLog(
                team_id=team_id,
                actor_user_id=uuid4(),
                actor_role="admin",
                entity_type="holerite",
                entity_id=uuid4(),
                action="rh.holerite.closed",
                before={"salario_base": "4500.00"},
                after={"salario_base": "***"},
                request_id="req-1",
                ip_hash="masked",
                user_agent="pytest",
            )
        ]

    async def count_by_filters(self, team_id, **filters):
        return 1


class _FakeSolicitacoesRepo:
    async def list_ajustes(self, current_user, filters, page, limit):
        return [object()], 1

    async def list_ferias(self, current_user, filters, page, limit):
        return [object()], 1

    async def list_atestados(self, current_user, filters, page, limit):
        return [object()], 1


class _FakeUow:
    async def commit(self):
        return None

    async def rollback(self):
        return None


class _FuncionarioStub:
    def __init__(self, team_id, user_id):
        self.id = uuid4()
        self.team_id = team_id
        self.user_id = user_id
        self.nome = "Ana Souza"
        self.is_active = True
        self.is_deleted = False


@pytest.mark.asyncio
async def test_obter_dashboard_returns_aggregated_counts():
    from app.application.services.rh_dashboard_service import RhDashboardService

    admin = _make_user(Roles.ADMIN)
    service = RhDashboardService(
        funcionario_repo=_FakeFuncionarioRepo(),
        ajuste_repo=_FakeAjusteRepo(),
        ferias_repo=_FakeFeriasRepo(),
        atestado_repo=_FakeAtestadoRepo(),
        registro_ponto_repo=_FakeRegistroRepo(),
        holerite_repo=_FakeHoleriteRepo(),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
    )

    dashboard = await service.obter_dashboard(admin, 4, 2026)

    assert dashboard.total_funcionarios_ativos == 12
    assert dashboard.holerites_fechados == 7
    assert dashboard.total_liquido_competencia == Decimal("25400.00")


@pytest.mark.asyncio
async def test_obter_meu_resumo_resolves_current_employee_only():
    from app.application.services.rh_dashboard_service import RhDashboardService

    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _FuncionarioStub(employee.team.id, employee.id)
    service = RhDashboardService(
        funcionario_repo=_FakeFuncionarioRepo(funcionario=funcionario),
        ajuste_repo=_FakeAjusteRepo(),
        ferias_repo=_FakeFeriasRepo(),
        atestado_repo=_FakeAtestadoRepo(),
        registro_ponto_repo=_FakeRegistroRepo(),
        holerite_repo=_FakeHoleriteRepo(),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
    )

    resumo = await service.obter_meu_resumo(employee)

    assert resumo.ajustes_pendentes == 1
    assert resumo.ultimo_holerite_fechado is not None
    assert resumo.ultimo_holerite_fechado.status == StatusHolerite.FECHADO


@pytest.mark.asyncio
async def test_obter_meu_resumo_accepts_admin_when_linked_to_funcionario():
    from app.application.services.rh_dashboard_service import RhDashboardService

    admin = _make_user(Roles.ADMIN)
    funcionario = _FuncionarioStub(admin.team.id, admin.id)
    service = RhDashboardService(
        funcionario_repo=_FakeFuncionarioRepo(funcionario=funcionario),
        ajuste_repo=_FakeAjusteRepo(),
        ferias_repo=_FakeFeriasRepo(),
        atestado_repo=_FakeAtestadoRepo(),
        registro_ponto_repo=_FakeRegistroRepo(),
        holerite_repo=_FakeHoleriteRepo(),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
    )

    resumo = await service.obter_meu_resumo(admin)

    assert resumo.ajustes_pendentes == 1
    assert resumo.ultimo_ponto is not None


@pytest.mark.asyncio
async def test_obter_meu_vinculo_returns_link_status_for_current_user():
    from app.application.services.rh_dashboard_service import RhDashboardService

    admin = _make_user(Roles.ADMIN)
    funcionario = _FuncionarioStub(admin.team.id, admin.id)
    service = RhDashboardService(
        funcionario_repo=_FakeFuncionarioRepo(funcionario=funcionario),
        ajuste_repo=_FakeAjusteRepo(),
        ferias_repo=_FakeFeriasRepo(),
        atestado_repo=_FakeAtestadoRepo(),
        registro_ponto_repo=_FakeRegistroRepo(),
        holerite_repo=_FakeHoleriteRepo(),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
    )

    vinculo = await service.obter_meu_vinculo(admin)

    assert vinculo["vinculado"] is True
    assert vinculo["funcionario_id"] == str(funcionario.id)


@pytest.mark.asyncio
async def test_listar_audit_logs_requires_rh_admin():
    from app.application.services.rh_dashboard_service import RhDashboardService

    employee = _make_user(Roles.FUNCIONARIO)
    service = RhDashboardService(
        funcionario_repo=_FakeFuncionarioRepo(),
        ajuste_repo=_FakeAjusteRepo(),
        ferias_repo=_FakeFeriasRepo(),
        atestado_repo=_FakeAtestadoRepo(),
        registro_ponto_repo=_FakeRegistroRepo(),
        holerite_repo=_FakeHoleriteRepo(),
        audit_repo=_FakeAuditRepo(),
        uow=_FakeUow(),
    )

    with pytest.raises(DomainError):
        await service.listar_audit_logs(employee, page=1, limit=20, filters={})
