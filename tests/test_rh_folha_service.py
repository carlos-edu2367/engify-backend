from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.financeiro import MovClass
from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    BaseCalculoEncargo,
    EscopoAplicabilidade,
    FaixaEncargo,
    Ferias,
    Funcionario,
    Holerite,
    HoleriteItem,
    HoleriteItemNatureza,
    HoleriteItemTipo,
    HorarioTrabalho,
    IntervaloHorario,
    NaturezaEncargo,
    RegraEncargo,
    RegraEncargoAplicabilidade,
    RegistroPonto,
    RhAuditLog,
    StatusRegraEncargo,
    StatusFerias,
    StatusHolerite,
    StatusPonto,
    TabelaProgressiva,
    TipoRegraEncargo,
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


class _FakeHoleriteItemRepo:
    def __init__(self) -> None:
        self.items_by_holerite = {}

    async def replace_automaticos(self, team_id, holerite_id, items):
        manual_items = [
            item
            for item in self.items_by_holerite.get((team_id, holerite_id), [])
            if not item.is_automatico
        ]
        self.items_by_holerite[(team_id, holerite_id)] = manual_items + list(items)
        return list(self.items_by_holerite[(team_id, holerite_id)])

    async def list_by_holerite(self, team_id, holerite_id):
        return list(self.items_by_holerite.get((team_id, holerite_id), []))


class _FakeRegraEncargoRepo:
    def __init__(self, regras=None) -> None:
        self.regras = list(regras or [])

    async def list_active_by_competencia(self, team_id, competencia):
        items = []
        for regra in self.regras:
            if regra.team_id != team_id:
                continue
            if regra.status != StatusRegraEncargo.ATIVA:
                continue
            if regra.vigencia_inicio and regra.vigencia_inicio > competencia:
                continue
            if regra.vigencia_fim and regra.vigencia_fim < competencia:
                continue
            items.append(regra)
        return items


class _FakeFolhaJobRepo:
    def __init__(self) -> None:
        self.jobs = {}

    async def save(self, job):
        self.jobs[job.id] = job
        return job

    async def get_by_id(self, team_id, job_id):
        job = self.jobs.get(job_id)
        if job is None or job.team_id != team_id:
            raise Exception("Job nao encontrado")
        return job

    async def get_by_id_unscoped(self, job_id):
        job = self.jobs.get(job_id)
        if job is None:
            raise Exception("Job nao encontrado")
        return job


class _FakeFolhaQueue:
    def __init__(self) -> None:
        self.enqueued = []

    async def enqueue_generate_folha(self, job_id):
        self.enqueued.append(job_id)


class _FakeEncargoCache:
    def __init__(self) -> None:
        self.cached = {}
        self.invalidated = []

    async def get_active_rules(self, team_id, ano, mes):
        return self.cached.get((team_id, ano, mes))

    async def set_active_rules(self, team_id, ano, mes, payload):
        self.cached[(team_id, ano, mes)] = payload

    async def invalidate_team(self, team_id):
        self.invalidated.append(team_id)


def _build_service(funcionarios, horarios, registros=None, ferias_items=None, holerites=None, regras=None):
    from app.application.services.rh_folha_service import RhFolhaService

    item_repo = _FakeHoleriteItemRepo()
    job_repo = _FakeFolhaJobRepo()
    job_queue = _FakeFolhaQueue()
    encargo_cache = _FakeEncargoCache()

    service = RhFolhaService(
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
        holerite_item_repo=item_repo,
        regra_encargo_repo=_FakeRegraEncargoRepo(regras),
        uow=_FakeUow(),
        folha_job_repo=job_repo,
        folha_queue=job_queue,
        encargo_cache=encargo_cache,
    )
    service.holerite_item_repo = item_repo
    service.folha_job_repo = job_repo
    service.folha_queue = job_queue
    service.encargo_cache = encargo_cache
    return service


def _regra_fixa(team_id, codigo="VA", natureza=NaturezaEncargo.PROVENTO, valor="500.00", inicio=None):
    return RegraEncargo(
        team_id=team_id,
        codigo=codigo,
        nome=f"Regra {codigo}",
        tipo_calculo=TipoRegraEncargo.VALOR_FIXO,
        natureza=natureza,
        base_calculo=BaseCalculoEncargo.VALOR_REFERENCIA_MANUAL,
        prioridade=500,
        valor_fixo=Money(Decimal(valor)),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=inicio or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _regra_percentual(team_id, codigo="VT", natureza=NaturezaEncargo.DESCONTO, percentual="6.00", inicio=None, aplicabilidades=None):
    return RegraEncargo(
        team_id=team_id,
        codigo=codigo,
        nome=f"Regra {codigo}",
        tipo_calculo=TipoRegraEncargo.PERCENTUAL_SIMPLES,
        natureza=natureza,
        base_calculo=BaseCalculoEncargo.SALARIO_BASE,
        prioridade=800,
        percentual=Decimal(percentual),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=inicio or datetime(2026, 1, 1, tzinfo=timezone.utc),
        aplicabilidades=aplicabilidades or [],
        incide_no_liquido=natureza != NaturezaEncargo.INFORMATIVO,
    )


def _regra_progressiva(team_id, codigo, tabela, base_calculo, prioridade):
    regra = RegraEncargo(
        team_id=team_id,
        codigo=codigo,
        nome=codigo,
        tipo_calculo=TipoRegraEncargo.TABELA_PROGRESSIVA,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=base_calculo,
        prioridade=prioridade,
        tabela_progressiva_id=tabela.id,
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    regra.tabela_progressiva = tabela
    return regra


def _ferias_mes(team_id, funcionario_id):
    return Ferias(
        team_id=team_id,
        funcionario_id=funcionario_id,
        data_inicio=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc),
        status=StatusFerias.APROVADO,
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


@pytest.mark.asyncio
async def test_generate_draft_mirrors_current_calculation_into_holerite_items():
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
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)

    assert [item.tipo for item in itens] == [
        HoleriteItemTipo.SALARIO_BASE,
        HoleriteItemTipo.HORA_EXTRA,
        HoleriteItemTipo.FALTA,
        HoleriteItemTipo.AJUSTE_MANUAL,
        HoleriteItemTipo.AJUSTE_MANUAL,
    ]
    assert [item.valor.amount for item in itens] == [
        result[0].salario_base.amount,
        result[0].horas_extras.amount,
        result[0].descontos_falta.amount,
        result[0].acrescimos_manuais.amount,
        result[0].descontos_manuais.amount,
    ]
    assert result[0].valor_liquido.amount == (
        result[0].salario_base.amount
        + result[0].horas_extras.amount
        + result[0].acrescimos_manuais.amount
        - result[0].descontos_falta.amount
        - result[0].descontos_manuais.amount
    )


@pytest.mark.asyncio
async def test_generate_draft_populates_aggregated_holerite_totals_without_changing_liquido():
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
        horas_extras=Money(Decimal("100.00")),
        descontos_falta=Money(Decimal("50.00")),
        acrescimos_manuais=Money(Decimal("40.00")),
        descontos_manuais=Money(Decimal("15.00")),
        valor_liquido=Money(Decimal("2275.00")),
    )
    service = _build_service([funcionario], {funcionario.id: horario}, holerites=[existing])

    result = await service.gerar_rascunho_folha(admin, 4, 2026)

    assert result[0].valor_bruto.amount == (
        result[0].salario_base.amount
        + result[0].horas_extras.amount
        + result[0].acrescimos_manuais.amount
        - result[0].descontos_falta.amount
    )
    assert result[0].total_proventos.amount == (
        result[0].salario_base.amount
        + result[0].horas_extras.amount
        + result[0].acrescimos_manuais.amount
    )
    assert result[0].total_descontos.amount == (
        result[0].descontos_falta.amount
        + result[0].descontos_manuais.amount
    )
    assert result[0].total_informativos.amount == Decimal("0.00")
    assert result[0].valor_liquido.amount == (
        result[0].total_proventos.amount - result[0].total_descontos.amount
    )


@pytest.mark.asyncio
async def test_generate_draft_applies_fixed_provento_rule():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[_regra_fixa(admin.team.id, codigo="VA", natureza=NaturezaEncargo.PROVENTO, valor="500.00")],
    )

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)

    assert any(item.codigo == "VA" for item in itens)
    assert result[0].valor_liquido.amount == Decimal("2700.00")


@pytest.mark.asyncio
async def test_generate_draft_applies_fixed_discount_rule():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[_regra_fixa(admin.team.id, codigo="VR", natureza=NaturezaEncargo.DESCONTO, valor="120.00")],
    )

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)

    assert result[0].total_descontos.amount == Decimal("120.00")
    assert result[0].valor_liquido.amount == Decimal("2080.00")


@pytest.mark.asyncio
async def test_generate_draft_applies_percentual_rule_and_fgts_informativo():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    fgts = _regra_percentual(
        admin.team.id,
        codigo="FGTS",
        natureza=NaturezaEncargo.INFORMATIVO,
        percentual="8.00",
    )
    fgts.base_calculo = BaseCalculoEncargo.BRUTO_ANTES_ENCARGOS
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[
            _regra_percentual(admin.team.id, codigo="VT", percentual="6.00"),
            fgts,
        ],
    )

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)
    fgts_item = next(item for item in itens if item.codigo == "FGTS")

    assert result[0].valor_liquido.amount == Decimal("2068.00")
    assert result[0].total_informativos.amount == Decimal("176.00")
    assert fgts_item.natureza == HoleriteItemNatureza.INFORMATIVO


@pytest.mark.asyncio
async def test_generate_draft_applies_progressive_inss_and_irrf_with_reduced_base():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    funcionario.salario_base = Money(Decimal("5000.00"))
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    inss_tabela = TabelaProgressiva(
        team_id=admin.team.id,
        codigo="INSS_2026",
        nome="INSS 2026",
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        faixas=[
            FaixaEncargo(
                team_id=admin.team.id,
                ordem=1,
                valor_inicial=Money(Decimal("0.00")),
                valor_final=Money(Decimal("5000.00")),
                aliquota=Decimal("11.00"),
            )
        ],
    )
    irrf_tabela = TabelaProgressiva(
        team_id=admin.team.id,
        codigo="IRRF_2026",
        nome="IRRF 2026",
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        faixas=[
            FaixaEncargo(
                team_id=admin.team.id,
                ordem=1,
                valor_inicial=Money(Decimal("0.00")),
                valor_final=Money(Decimal("10000.00")),
                aliquota=Decimal("15.00"),
                deducao=Money(Decimal("100.00")),
            )
        ],
    )
    regras = [
        _regra_progressiva(admin.team.id, "INSS", inss_tabela, BaseCalculoEncargo.BRUTO_ANTES_ENCARGOS, 600),
        _regra_progressiva(admin.team.id, "IRRF", irrf_tabela, BaseCalculoEncargo.BRUTO_ANTES_IRRF, 700),
    ]
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=regras,
    )

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)
    irrf_item = next(item for item in itens if item.codigo == "IRRF")

    assert irrf_item.base.amount == Decimal("4450.00")
    assert irrf_item.valor.amount == Decimal("567.50")
    assert result[0].valor_liquido.amount == Decimal("3882.50")


@pytest.mark.asyncio
async def test_generate_draft_respects_rule_vigencia_and_employee_override():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    geral = _regra_percentual(
        admin.team.id,
        codigo="VT",
        percentual="6.00",
        aplicabilidades=[RegraEncargoAplicabilidade(team_id=admin.team.id, escopo=EscopoAplicabilidade.TODOS_FUNCIONARIOS)],
    )
    especifica = _regra_percentual(
        admin.team.id,
        codigo="VT",
        percentual="4.00",
        aplicabilidades=[
            RegraEncargoAplicabilidade(
                team_id=admin.team.id,
                escopo=EscopoAplicabilidade.POR_FUNCIONARIO,
                valor=str(funcionario.id),
            )
        ],
    )
    futura = _regra_fixa(
        admin.team.id,
        codigo="VA_FUTURO",
        natureza=NaturezaEncargo.PROVENTO,
        valor="100.00",
        inicio=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[geral, especifica, futura],
    )

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)

    assert [item.codigo for item in itens if item.codigo.startswith("VT")] == ["VT"]
    assert next(item for item in itens if item.codigo == "VT").valor.amount == Decimal("88.00")
    assert all(item.codigo != "VA_FUTURO" for item in itens)


@pytest.mark.asyncio
async def test_generate_draft_preserves_manual_items_when_replacing_automatic_items():
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
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        valor_liquido=Money(Decimal("2200.00")),
    )
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        holerites=[existing],
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[_regra_fixa(admin.team.id, codigo="VA", natureza=NaturezaEncargo.PROVENTO, valor="100.00")],
    )
    service.holerite_item_repo.items_by_holerite[(admin.team.id, existing.id)] = [
        HoleriteItem(
            team_id=admin.team.id,
            holerite_id=existing.id,
            funcionario_id=funcionario.id,
            tipo=HoleriteItemTipo.AJUSTE_MANUAL,
            origem="manual",
            codigo="BONUS_EXTRA",
            descricao="Bonus Manual",
            natureza=HoleriteItemNatureza.PROVENTO,
            ordem=450,
            valor=Money(Decimal("50.00")),
            is_automatico=False,
        )
    ]

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)

    assert any(item.codigo == "BONUS_EXTRA" for item in itens)
    assert any(item.codigo == "VA" for item in itens)


@pytest.mark.asyncio
async def test_generate_draft_blocks_recalculation_for_closed_holerite():
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
        acrescimos_manuais=Money(Decimal("0.00")),
        descontos_manuais=Money(Decimal("0.00")),
        valor_liquido=Money(Decimal("2200.00")),
        status=StatusHolerite.FECHADO,
    )
    service = _build_service([funcionario], {funcionario.id: horario}, holerites=[existing])

    with pytest.raises(Exception):
        await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)


@pytest.mark.asyncio
async def test_generate_draft_is_idempotent_when_inputs_do_not_change():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[_regra_percentual(admin.team.id, codigo="VT", percentual="6.00")],
    )

    first = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    second = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)

    assert first[0].calculation_hash is not None
    assert first[0].calculation_hash == second[0].calculation_hash
    assert first[0].valor_liquido == second[0].valor_liquido


@pytest.mark.asyncio
async def test_generate_draft_keeps_rules_isolated_by_team():
    admin = _make_user(Roles.ADMIN)
    other_team_id = uuid4()
    funcionario = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    service = _build_service(
        [funcionario],
        {funcionario.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario.id)],
        regras=[
            _regra_fixa(other_team_id, codigo="VA_X", natureza=NaturezaEncargo.PROVENTO, valor="999.00"),
            _regra_fixa(admin.team.id, codigo="VA_OK", natureza=NaturezaEncargo.PROVENTO, valor="100.00"),
        ],
    )

    result = await service.gerar_rascunho_folha(admin, 4, 2026, funcionario_id=funcionario.id)
    itens = await service.holerite_item_repo.list_by_holerite(admin.team.id, result[0].id)

    assert any(item.codigo == "VA_OK" for item in itens)
    assert all(item.codigo != "VA_X" for item in itens)


@pytest.mark.asyncio
async def test_folha_job_supports_partial_success_and_failures_per_employee():
    admin = _make_user(Roles.ADMIN)
    funcionario_ok = _make_funcionario(admin.team.id)
    funcionario_falha = _make_funcionario(admin.team.id)
    horario = HorarioTrabalho(
        team_id=admin.team.id,
        funcionario_id=funcionario_ok.id,
        turnos=[TurnoHorario(dia_semana=0, hora_entrada=time(8, 0), hora_saida=time(17, 0))],
    )
    service = _build_service(
        [funcionario_ok, funcionario_falha],
        {funcionario_ok.id: horario},
        ferias_items=[_ferias_mes(admin.team.id, funcionario_ok.id)],
    )

    job = await service.criar_job_geracao_folha(admin, 4, 2026)
    processed = await service.processar_job_geracao_folha(job.id)

    assert service.folha_queue.enqueued == [job.id]
    assert processed.status.value == "concluido_com_falhas"
    assert processed.total_funcionarios == 2
    assert processed.processados == 2
    assert processed.falhas == 1
    assert len(processed.error_summary) == 1
    assert processed.error_summary[0]["funcionario_id"] == str(funcionario_falha.id)
