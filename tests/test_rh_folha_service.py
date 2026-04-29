from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.financeiro import MovClass
from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    Ferias,
    Funcionario,
    Holerite,
    HorarioTrabalho,
    IntervaloHorario,
    RegistroPonto,
    RhAuditLog,
    StatusFerias,
    StatusHolerite,
    StatusPonto,
    TipoPonto,
    TurnoHorario,
)
from app.domain.entities.team import Plans, Team
from app.domain.entities.user import Roles, User


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
    funcionario = Funcionario(
        team_id=team_id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("2200.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
        user_id=user_id,
    )
    return funcionario


class _FakeFuncionarioRepo:
    def __init__(self, funcionarios) -> None:
        self.funcionarios = list(funcionarios)

    async def get_by_id(self, id, team_id):
        for funcionario in self.funcionarios:
            if funcionario.id == id and funcionario.team_id == team_id and not funcionario.is_deleted:
                return funcionario
        raise Exception("Funcionario nao encontrado")

    async def get_by_user_id(self, team_id, user_id):
        for funcionario in self.funcionarios:
            if funcionario.team_id == team_id and funcionario.user_id == user_id and not funcionario.is_deleted:
                return funcionario
        return None

    async def list_active_by_team(self, team_id, limit, offset):
        items = [item for item in self.funcionarios if item.team_id == team_id and item.is_active and not item.is_deleted]
        return items[offset : offset + limit]


class _FakeHorarioRepo:
    def __init__(self, horarios) -> None:
        self.horarios = horarios

    async def list_by_funcionarios(self, team_id, funcionario_ids):
        return {
            funcionario_id: horario
            for funcionario_id, horario in self.horarios.items()
            if horario.team_id == team_id and funcionario_id in funcionario_ids and not horario.is_deleted
        }


class _FakeRegistroRepo:
    def __init__(self, registros) -> None:
        self.registros = list(registros)

    async def list_by_competencia(self, team_id, funcionario_ids, start, end):
        return [
            item
            for item in self.registros
            if item.team_id == team_id
            and item.funcionario_id in funcionario_ids
            and start <= item.timestamp <= end
            and item.status in {StatusPonto.VALIDADO, StatusPonto.AJUSTADO, StatusPonto.INCONSISTENTE}
        ]


class _FakeFeriasRepo:
    def __init__(self, ferias_items) -> None:
        self.ferias_items = list(ferias_items)

    async def list_by_competencia(self, team_id, funcionario_ids, start, end, statuses):
        allowed = {status.value if hasattr(status, "value") else status for status in statuses}
        return [
            item
            for item in self.ferias_items
            if item.team_id == team_id
            and item.funcionario_id in funcionario_ids
            and item.status.value in allowed
            and item.data_inicio <= end
            and item.data_fim >= start
            and not item.is_deleted
        ]


class _FakeAtestadoRepo:
    def __init__(self, atestados) -> None:
        self.atestados = list(atestados)

    async def list_by_competencia(self, team_id, funcionario_ids, start, end, statuses):
        return []


class _FakeTipoAtestadoRepo:
    async def get_by_id(self, id, team_id):
        raise AssertionError("Nao deveria consultar tipos de atestado neste teste")


class _FakeHoleriteRepo:
    def __init__(self, holerites=None) -> None:
        self.holerites = list(holerites or [])

    async def get_by_id(self, id, team_id):
        for holerite in self.holerites:
            if holerite.id == id and holerite.team_id == team_id and not holerite.is_deleted:
                return holerite
        raise Exception("Holerite nao encontrado")

    async def get_by_competencia(self, team_id, funcionario_id, mes, ano):
        for holerite in self.holerites:
            if (
                holerite.team_id == team_id
                and holerite.funcionario_id == funcionario_id
                and holerite.mes_referencia == mes
                and holerite.ano_referencia == ano
                and not holerite.is_deleted
            ):
                return holerite
        return None

    async def list_by_competencia(self, team_id, mes, ano, status=None, page=1, limit=50, funcionario_id=None):
        items = [
            item
            for item in self.holerites
            if item.team_id == team_id
            and item.mes_referencia == mes
            and item.ano_referencia == ano
            and not item.is_deleted
            and (status is None or item.status == status)
            and (funcionario_id is None or item.funcionario_id == funcionario_id)
        ]
        return items[(page - 1) * limit : page * limit]

    async def count_by_competencia(self, team_id, mes, ano, status=None, funcionario_id=None):
        items = await self.list_by_competencia(team_id, mes, ano, status=status, page=1, limit=1000, funcionario_id=funcionario_id)
        return len(items)

    async def list_rascunhos_by_competencia(self, team_id, mes, ano, limit=500, funcionario_ids=None):
        items = [
            item
            for item in self.holerites
            if item.team_id == team_id
            and item.mes_referencia == mes
            and item.ano_referencia == ano
            and item.status == StatusHolerite.RASCUNHO
            and not item.is_deleted
            and (funcionario_ids is None or item.funcionario_id in funcionario_ids)
        ]
        return items[:limit]

    async def save(self, holerite):
        self.holerites = [item for item in self.holerites if item.id != holerite.id]
        self.holerites.append(holerite)
        return holerite


class _FakePagamentoRepo:
    def __init__(self) -> None:
        self.items = []

    async def save(self, pagamento):
        if pagamento.id is None:
            pagamento.id = uuid4()
        self.items.append(pagamento)
        return pagamento


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log


class _FakeIdempotencyRepo:
    def __init__(self) -> None:
        self.keys = set()

    async def exists_or_create(self, team_id, scope, key):
        compound = (str(team_id), scope, key)
        if compound in self.keys:
            return True
        self.keys.add(compound)
        return False


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def _build_service(funcionarios, horarios, registros=None, ferias_items=None, holerites=None):
    from app.application.services.rh_folha_service import RhFolhaService

    return RhFolhaService(
        funcionario_repo=_FakeFuncionarioRepo(funcionarios),
        horario_repo=_FakeHorarioRepo(horarios),
        registro_ponto_repo=_FakeRegistroRepo(registros or []),
        ferias_repo=_FakeFeriasRepo(ferias_items or []),
        tipo_atestado_repo=_FakeTipoAtestadoRepo(),
        atestado_repo=_FakeAtestadoRepo([]),
        holerite_repo=_FakeHoleriteRepo(holerites or []),
        pagamento_repo=_FakePagamentoRepo(),
        audit_repo=_FakeAuditRepo(),
        idempotency_repo=_FakeIdempotencyRepo(),
        uow=_FakeUow(),
    )


@pytest.mark.asyncio
async def test_generate_draft_preserves_manual_adjustments_on_existing_holerite():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    existing = Holerite(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        mes_referencia=4,
        ano_referencia=2026,
        salario_base=Money(Decimal("2200.00")),
        horas_extras=Money(Decimal("0.00")),
        descontos_falta=Money(Decimal("0.00")),
        acrescimos_manuais=Money(Decimal("40.00")),
        descontos_manuais=Money(Decimal("15.00")),
        valor_liquido=Money(Decimal("2225.00")),
    )
    service = _build_service([funcionario], {funcionario.id: horario}, holerites=[existing])

    result = await service.gerar_rascunho_folha(admin, 4, 2026)

    assert result[0].acrescimos_manuais.amount == Decimal("40.00")
    assert result[0].descontos_manuais.amount == Decimal("15.00")
    assert result[0].status == StatusHolerite.RASCUNHO


@pytest.mark.asyncio
async def test_generate_draft_does_not_discount_absence_covered_by_approved_ferias():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=3, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    ferias = Ferias(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        data_inicio=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc),
        status=StatusFerias.APROVADO,
    )
    service = _build_service([funcionario], {funcionario.id: horario}, ferias_items=[ferias])

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)

    assert result[0].descontos_falta.amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_generate_draft_discounts_scheduled_interval_from_expected_and_worked_hours():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    funcionario.salario_base = Money(Decimal("1760.00"))
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[
            TurnoHorario(
                dia_semana=0,
                hora_entrada=time(8, 0),
                hora_saida=time(17, 0),
                intervalos=[IntervaloHorario(hora_inicio=time(12, 0), hora_fim=time(13, 0))],
            )
        ],
    )
    registros = []
    for day in [6, 13, 20, 27]:
        registros.extend(
            [
                RegistroPonto(
                    team_id=admin.team.id,
                    funcionario_id=funcionario.id,
                    tipo=TipoPonto.ENTRADA,
                    timestamp=datetime(2026, 4, day, 8, 0, tzinfo=timezone.utc),
                    latitude=0,
                    longitude=0,
                ),
                RegistroPonto(
                    team_id=admin.team.id,
                    funcionario_id=funcionario.id,
                    tipo=TipoPonto.SAIDA,
                    timestamp=datetime(2026, 4, day, 17, 0, tzinfo=timezone.utc),
                    latitude=0,
                    longitude=0,
                ),
            ]
        )
    service = _build_service([funcionario], {funcionario.id: horario}, registros=registros)

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)

    assert result[0].horas_extras.amount == Decimal("0.00")
    assert result[0].descontos_falta.amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_generate_draft_counts_absence_using_net_expected_hours_with_interval():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    funcionario.salario_base = Money(Decimal("1760.00"))
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[
            TurnoHorario(
                dia_semana=0,
                hora_entrada=time(8, 0),
                hora_saida=time(17, 0),
                intervalos=[IntervaloHorario(hora_inicio=time(12, 0), hora_fim=time(13, 0))],
            )
        ],
    )
    service = _build_service([funcionario], {funcionario.id: horario})

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)

    assert result[0].descontos_falta.amount == Decimal("1760.00")


@pytest.mark.asyncio
async def test_close_folha_is_idempotent_and_creates_operational_payment_once():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    holerite = Holerite(
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
    )
    service = _build_service([funcionario], {funcionario.id: horario}, holerites=[holerite])

    first_result = await service.fechar_folha(admin, 4, 2026, idempotency_key="same-key")
    second_result = await service.fechar_folha(admin, 4, 2026, idempotency_key="same-key")

    assert first_result[0].status == StatusHolerite.FECHADO
    assert second_result[0].status == StatusHolerite.FECHADO
    assert first_result[0].pagamento_agendado_id == second_result[0].pagamento_agendado_id
    assert len(service.pagamento_repo.items) == 1
    assert service.pagamento_repo.items[0].classe == MovClass.OPERACIONAL
