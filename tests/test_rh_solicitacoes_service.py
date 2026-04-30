from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.dtos.rh import (
    CreateAjustePontoDTO,
    CreateAtestadoDTO,
    CreateFeriasDTO,
    CreateTipoAtestadoDTO,
)
from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    AjustePonto,
    Atestado,
    Ferias,
    Funcionario,
    RegistroPonto,
    RhAuditLog,
    StatusAjuste,
    StatusAtestado,
    StatusFerias,
    StatusPonto,
    TipoAtestado,
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


def _make_funcionario(team_id, user_id=None, is_active=True) -> Funcionario:
    return Funcionario(
        team_id=team_id,
        nome="Ana Souza",
        cpf=CPF("11144477735"),
        cargo="Analista",
        salario_base=Money(Decimal("4500.00")),
        data_admissao=datetime(2026, 4, 1, tzinfo=timezone.utc),
        user_id=user_id,
        is_active=is_active,
    )


class _FakeFuncionarioRepo:
    def __init__(self, funcionarios=None) -> None:
        self.by_id = {item.id: item for item in funcionarios or []}

    async def get_by_id(self, id, team_id):
        item = self.by_id.get(id)
        if not item or item.team_id != team_id or item.is_deleted:
            raise DomainError("Funcionario nao encontrado")
        return item

    async def get_by_user_id(self, team_id, user_id):
        for item in self.by_id.values():
            if item.team_id == team_id and item.user_id == user_id and not item.is_deleted:
                return item
        return None


class _FakeFeriasRepo:
    def __init__(self, items=None, overlap=False) -> None:
        self.items = list(items or [])
        self.overlap = overlap

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Ferias nao encontradas")

    async def save(self, ferias):
        self.items = [item for item in self.items if item.id != ferias.id]
        self.items.append(ferias)
        return ferias

    async def has_overlap(self, team_id, funcionario_id, start, end, statuses, exclude_id=None):
        return self.overlap

    async def list_by_filters(self, team_id, page, limit, **filters):
        return self.items[(page - 1) * limit : page * limit]

    async def count_by_filters(self, team_id, **filters):
        return len(self.items)


class _FakeAjusteRepo:
    def __init__(self, items=None, duplicate=False) -> None:
        self.items = list(items or [])
        self.duplicate = duplicate

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Ajuste de ponto nao encontrado")

    async def save(self, ajuste):
        self.items = [item for item in self.items if item.id != ajuste.id]
        self.items.append(ajuste)
        return ajuste

    async def has_pending_duplicate(self, team_id, funcionario_id, data_referencia, entrada, saida):
        return self.duplicate

    async def list_by_filters(self, team_id, page, limit, **filters):
        return self.items[(page - 1) * limit : page * limit]

    async def count_by_filters(self, team_id, **filters):
        return len(self.items)


class _FakeRegistroRepo:
    def __init__(self, items=None) -> None:
        self.items = list(items or [])

    async def list_by_funcionario_day(self, team_id, funcionario_id, day_start, day_end):
        return [
            item
            for item in self.items
            if item.team_id == team_id and item.funcionario_id == funcionario_id and day_start <= item.timestamp <= day_end
        ]

    async def save(self, registro):
        self.items = [item for item in self.items if item.id != registro.id]
        self.items.append(registro)
        return registro


class _FakeTipoAtestadoRepo:
    def __init__(self, items=None) -> None:
        self.items = list(items or [])

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Tipo de atestado nao encontrado")

    async def save(self, tipo):
        self.items = [item for item in self.items if item.id != tipo.id]
        self.items.append(tipo)
        return tipo

    async def list_active(self, team_id, page, limit):
        items = [item for item in self.items if item.team_id == team_id and not item.is_deleted]
        return items[(page - 1) * limit : page * limit]

    async def count_active(self, team_id):
        return len([item for item in self.items if item.team_id == team_id and not item.is_deleted])


class _FakeAtestadoRepo:
    def __init__(self, items=None) -> None:
        self.items = list(items or [])

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Atestado nao encontrado")

    async def save(self, atestado):
        self.items = [item for item in self.items if item.id != atestado.id]
        self.items.append(atestado)
        return atestado

    async def list_due_for_expiration(self, now, limit=500, team_id=None):
        return [
            item
            for item in self.items
            if item.status == StatusAtestado.AGUARDANDO_ENTREGA and (team_id is None or item.team_id == team_id)
        ][:limit]

    async def list_by_filters(self, team_id, page, limit, **filters):
        return self.items[(page - 1) * limit : page * limit]

    async def count_by_filters(self, team_id, **filters):
        return len(self.items)


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def _make_service(funcionario, **overrides):
    from app.application.services.rh_solicitacoes_service import RhSolicitacoesService

    return RhSolicitacoesService(
        funcionario_repo=overrides.get("funcionario_repo", _FakeFuncionarioRepo([funcionario])),
        ferias_repo=overrides.get("ferias_repo", _FakeFeriasRepo()),
        ajuste_repo=overrides.get("ajuste_repo", _FakeAjusteRepo()),
        registro_ponto_repo=overrides.get("registro_repo", _FakeRegistroRepo()),
        tipo_atestado_repo=overrides.get("tipo_repo", _FakeTipoAtestadoRepo()),
        atestado_repo=overrides.get("atestado_repo", _FakeAtestadoRepo()),
        audit_repo=overrides.get("audit_repo", _FakeAuditRepo()),
        uow=overrides.get("uow", _FakeUow()),
    )


@pytest.mark.asyncio
async def test_funcionario_requests_ferias_for_self_and_audits():
    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    audit_repo = _FakeAuditRepo()
    service = _make_service(funcionario, audit_repo=audit_repo)

    ferias = await service.request_ferias(
        CreateFeriasDTO(
            funcionario_id=None,
            data_inicio=datetime(2026, 5, 1, tzinfo=timezone.utc),
            data_fim=datetime(2026, 5, 10, tzinfo=timezone.utc),
        ),
        current_user,
    )

    assert ferias.funcionario_id == funcionario.id
    assert ferias.status == StatusFerias.SOLICITADO
    assert audit_repo.events[-1].action == "rh.ferias.requested"


@pytest.mark.asyncio
async def test_admin_linked_to_funcionario_requests_ferias_for_self_without_funcionario_id():
    current_user = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    service = _make_service(funcionario)

    ferias = await service.request_ferias(
        CreateFeriasDTO(
            funcionario_id=None,
            data_inicio=datetime(2026, 5, 1, tzinfo=timezone.utc),
            data_fim=datetime(2026, 5, 10, tzinfo=timezone.utc),
        ),
        current_user,
    )

    assert ferias.funcionario_id == funcionario.id
    assert ferias.status == StatusFerias.SOLICITADO


@pytest.mark.asyncio
async def test_approve_ferias_revalidates_overlap():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    ferias = Ferias(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        data_inicio=datetime(2026, 5, 1, tzinfo=timezone.utc),
        data_fim=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    service = _make_service(funcionario, ferias_repo=_FakeFeriasRepo([ferias], overlap=True))

    with pytest.raises(DomainError):
        await service.approve_ferias(ferias.id, admin)


@pytest.mark.asyncio
async def test_approve_ajuste_marks_existing_day_records_as_adjusted():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    ajuste = AjustePonto(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        data_referencia=datetime(2026, 4, 28, tzinfo=timezone.utc),
        justificativa="Esqueci a saida",
        hora_saida_solicitada=datetime(2026, 4, 28, 17, 0, tzinfo=timezone.utc),
    )
    registro = RegistroPonto(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        tipo=TipoPonto.ENTRADA,
        timestamp=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
        latitude=-16.68,
        longitude=-49.26,
    )
    registro_repo = _FakeRegistroRepo([registro])
    service = _make_service(
        funcionario,
        ajuste_repo=_FakeAjusteRepo([ajuste]),
        registro_repo=registro_repo,
    )

    approved = await service.approve_ajuste(ajuste.id, admin)

    assert approved.status == StatusAjuste.APROVADO
    assert registro_repo.items[0].status == StatusPonto.AJUSTADO
    assert any(item.tipo == TipoPonto.SAIDA and item.status == StatusPonto.AJUSTADO for item in registro_repo.items)


@pytest.mark.asyncio
async def test_job_expires_only_overdue_atestados():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    tipo = TipoAtestado(team_id=admin.team.id, nome="Medico", prazo_entrega_dias=1)
    overdue = Atestado(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        tipo_atestado_id=tipo.id,
        data_inicio=datetime(2026, 4, 20, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    overdue.created_at = datetime(2026, 4, 20, tzinfo=timezone.utc)
    recent = Atestado(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        tipo_atestado_id=tipo.id,
        data_inicio=datetime(2026, 4, 28, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 28, tzinfo=timezone.utc),
    )
    recent.created_at = datetime(2026, 4, 28, 12, tzinfo=timezone.utc)
    atestado_repo = _FakeAtestadoRepo([overdue, recent])
    service = _make_service(
        funcionario,
        tipo_repo=_FakeTipoAtestadoRepo([tipo]),
        atestado_repo=atestado_repo,
    )

    expired = await service.expire_overdue_atestados(datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc))

    assert expired == 1
    assert overdue.status == StatusAtestado.VENCIDO
    assert recent.status == StatusAtestado.AGUARDANDO_ENTREGA


@pytest.mark.asyncio
async def test_create_tipo_atestado_is_restricted_to_rh_admin():
    employee = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(employee.team.id, user_id=employee.id)
    service = _make_service(funcionario)

    with pytest.raises(DomainError):
        await service.create_tipo_atestado(
            CreateTipoAtestadoDTO(nome="Medico", prazo_entrega_dias=2, abona_falta=True, descricao=None),
            employee,
        )


@pytest.mark.asyncio
async def test_funcionario_creates_own_atestado():
    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    tipo = TipoAtestado(team_id=current_user.team.id, nome="Medico", prazo_entrega_dias=2)
    service = _make_service(funcionario, tipo_repo=_FakeTipoAtestadoRepo([tipo]))

    atestado = await service.create_atestado(
        CreateAtestadoDTO(
            funcionario_id=None,
            tipo_atestado_id=tipo.id,
            data_inicio=datetime(2026, 4, 28, tzinfo=timezone.utc),
            data_fim=datetime(2026, 4, 29, tzinfo=timezone.utc),
            file_path=None,
        ),
        current_user,
    )

    assert atestado.funcionario_id == funcionario.id
    assert atestado.status == StatusAtestado.AGUARDANDO_ENTREGA


@pytest.mark.asyncio
async def test_obter_atestado_para_download_allows_only_owner_employee():
    current_user = _make_user(Roles.FUNCIONARIO)
    funcionario = _make_funcionario(current_user.team.id, user_id=current_user.id)
    outro_funcionario = _make_funcionario(current_user.team.id)
    tipo = TipoAtestado(team_id=current_user.team.id, nome="Medico", prazo_entrega_dias=2)
    atestado = Atestado(
        team_id=current_user.team.id,
        funcionario_id=outro_funcionario.id,
        tipo_atestado_id=tipo.id,
        data_inicio=datetime(2026, 4, 28, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 29, tzinfo=timezone.utc),
        file_path="rh/atestado.pdf",
    )
    service = _make_service(
        funcionario,
        tipo_repo=_FakeTipoAtestadoRepo([tipo]),
        atestado_repo=_FakeAtestadoRepo([atestado]),
    )

    with pytest.raises(DomainError):
        await service.obter_atestado_para_download(atestado.id, current_user)


@pytest.mark.asyncio
async def test_obter_atestado_para_download_rejects_missing_file():
    admin = _make_user(Roles.ADMIN)
    funcionario = _make_funcionario(admin.team.id)
    tipo = TipoAtestado(team_id=admin.team.id, nome="Medico", prazo_entrega_dias=2)
    atestado = Atestado(
        team_id=admin.team.id,
        funcionario_id=funcionario.id,
        tipo_atestado_id=tipo.id,
        data_inicio=datetime(2026, 4, 28, tzinfo=timezone.utc),
        data_fim=datetime(2026, 4, 29, tzinfo=timezone.utc),
    )
    service = _make_service(
        funcionario,
        tipo_repo=_FakeTipoAtestadoRepo([tipo]),
        atestado_repo=_FakeAtestadoRepo([atestado]),
    )

    with pytest.raises(DomainError):
        await service.obter_atestado_para_download(atestado.id, admin)
