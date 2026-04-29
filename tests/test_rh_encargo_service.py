from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.identities import CPF
from app.domain.entities.money import Money
from app.domain.entities.rh import (
    BaseCalculoEncargo,
    EscopoAplicabilidade,
    FaixaEncargo,
    NaturezaEncargo,
    RegraEncargo,
    RegraEncargoAplicabilidade,
    RhAuditLog,
    StatusRegraEncargo,
    TabelaProgressiva,
    TipoRegraEncargo,
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


def _make_user(role: Roles = Roles.ADMIN, team_id=None) -> User:
    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Carlos"
    user.email = "carlos@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = _make_team(team_id)
    user.cpf = CPF("52998224725")
    return user


class _FakeRegraRepo:
    def __init__(self) -> None:
        self.items: list[RegraEncargo] = []

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Regra de encargo nao encontrada")

    async def list_by_filters(self, team_id, page, limit, **filters):
        items = [item for item in self.items if item.team_id == team_id and not item.is_deleted]
        status = filters.get("status")
        if status is not None:
            items = [item for item in items if item.status == status]
        return items[(page - 1) * limit : page * limit]

    async def count_by_filters(self, team_id, **filters):
        return len(await self.list_by_filters(team_id, 1, 10_000, **filters))

    async def has_active_conflict(self, team_id, regra_grupo_id, codigo, vigencia_inicio, vigencia_fim, aplicabilidades, exclude_id=None):
        for item in self.items:
            if item.team_id != team_id or item.id == exclude_id or item.is_deleted:
                continue
            if item.status != StatusRegraEncargo.ATIVA or item.codigo != codigo:
                continue
            if item.regra_grupo_id != regra_grupo_id:
                continue
            if not _overlaps(vigencia_inicio, vigencia_fim, item.vigencia_inicio, item.vigencia_fim):
                continue
            if {(a.escopo, a.valor) for a in item.aplicabilidades} == {(a.escopo, a.valor) for a in aplicabilidades}:
                return True
        return False

    async def save(self, regra):
        self.items = [item for item in self.items if item.id != regra.id]
        self.items.append(regra)
        return regra


class _FakeTabelaRepo:
    def __init__(self) -> None:
        self.items: list[TabelaProgressiva] = []
        self.used_active_ids: set = set()

    async def get_by_id(self, id, team_id):
        for item in self.items:
            if item.id == id and item.team_id == team_id and not item.is_deleted:
                return item
        raise DomainError("Tabela progressiva nao encontrada")

    async def list_by_filters(self, team_id, page, limit, **filters):
        items = [item for item in self.items if item.team_id == team_id and not item.is_deleted]
        return items[(page - 1) * limit : page * limit]

    async def count_by_filters(self, team_id, **filters):
        return len(await self.list_by_filters(team_id, 1, 10_000, **filters))

    async def is_used_by_active_rule(self, team_id, tabela_id):
        return tabela_id in self.used_active_ids

    async def save(self, tabela):
        self.items = [item for item in self.items if item.id != tabela.id]
        self.items.append(tabela)
        return tabela


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[RhAuditLog] = []

    async def save(self, audit_log):
        self.events.append(audit_log)
        return audit_log


class _FakeCache:
    def __init__(self) -> None:
        self.invalidated = []

    async def invalidate_team(self, team_id):
        self.invalidated.append(team_id)


class _FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def _overlaps(start_a, end_a, start_b, end_b):
    open_end = datetime.max.replace(tzinfo=timezone.utc)
    return start_a <= (end_b or open_end) and (end_a or open_end) >= start_b


def _build_service():
    from app.application.services.rh_encargo_service import RhEncargoService

    regra_repo = _FakeRegraRepo()
    tabela_repo = _FakeTabelaRepo()
    audit_repo = _FakeAuditRepo()
    cache = _FakeCache()
    uow = _FakeUow()
    service = RhEncargoService(
        regra_repo=regra_repo,
        tabela_repo=tabela_repo,
        audit_repo=audit_repo,
        uow=uow,
        encargo_cache=cache,
    )
    return service, regra_repo, tabela_repo, audit_repo, cache, uow


def _regra_payload(**overrides):
    payload = {
        "codigo": "INSS",
        "nome": "INSS",
        "tipo_calculo": TipoRegraEncargo.PERCENTUAL_SIMPLES,
        "natureza": NaturezaEncargo.DESCONTO,
        "base_calculo": BaseCalculoEncargo.SALARIO_BASE,
        "prioridade": 100,
        "percentual": Decimal("11.00"),
        "vigencia_inicio": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "aplicabilidades": [
            RegraEncargoAplicabilidade(team_id=uuid4(), escopo=EscopoAplicabilidade.TODOS_FUNCIONARIOS)
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_regra_lifecycle_creates_draft_activates_inactivates_and_versions():
    admin = _make_user()
    service, regra_repo, _, audit_repo, cache, uow = _build_service()

    regra = await service.criar_regra(admin, _regra_payload())
    assert regra.status == StatusRegraEncargo.RASCUNHO
    activated = await service.ativar_regra(admin, regra.id, "Publicacao legal")
    assert activated.status == StatusRegraEncargo.ATIVA
    inactivated = await service.inativar_regra(admin, regra.id, "Substituida")
    new_version = await service.criar_nova_versao(admin, regra.id, {"percentual": Decimal("12.00")})

    assert inactivated.status == StatusRegraEncargo.INATIVA
    assert new_version.status == StatusRegraEncargo.RASCUNHO
    assert new_version.regra_grupo_id == regra.regra_grupo_id
    assert new_version.percentual == Decimal("12.00")
    assert [event.action for event in audit_repo.events] == [
        "rh.regra_encargo.created",
        "rh.regra_encargo.activated",
        "rh.regra_encargo.inactivated",
        "rh.regra_encargo.version_created",
    ]
    assert cache.invalidated == [admin.team.id, admin.team.id, admin.team.id]
    assert uow.commits == 4
    assert len(regra_repo.items) == 2


@pytest.mark.asyncio
async def test_ativar_regra_rejects_vigencia_conflict_for_same_group_and_scope():
    admin = _make_user()
    service, regra_repo, _, _, _, _ = _build_service()
    aplicabilidade = RegraEncargoAplicabilidade(team_id=admin.team.id, escopo=EscopoAplicabilidade.TODOS_FUNCIONARIOS)
    active = RegraEncargo(
        team_id=admin.team.id,
        codigo="INSS",
        nome="INSS 2026",
        tipo_calculo=TipoRegraEncargo.PERCENTUAL_SIMPLES,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.SALARIO_BASE,
        prioridade=100,
        percentual=Decimal("11.00"),
        status=StatusRegraEncargo.ATIVA,
        vigencia_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
        aplicabilidades=[aplicabilidade],
    )
    draft = RegraEncargo(
        team_id=admin.team.id,
        codigo="INSS",
        nome="INSS 2026 nova",
        tipo_calculo=TipoRegraEncargo.PERCENTUAL_SIMPLES,
        natureza=NaturezaEncargo.DESCONTO,
        base_calculo=BaseCalculoEncargo.SALARIO_BASE,
        prioridade=100,
        percentual=Decimal("12.00"),
        vigencia_inicio=datetime(2026, 6, 1, tzinfo=timezone.utc),
        regra_grupo_id=active.regra_grupo_id,
        aplicabilidades=[RegraEncargoAplicabilidade(team_id=admin.team.id, escopo=EscopoAplicabilidade.TODOS_FUNCIONARIOS)],
    )
    await regra_repo.save(active)
    await regra_repo.save(draft)

    with pytest.raises(DomainError, match="conflito de vigencia"):
        await service.ativar_regra(admin, draft.id, "Nova tabela")


@pytest.mark.asyncio
async def test_tabela_progressiva_rejects_empty_and_overlapping_ranges_and_blocks_active_edit():
    admin = _make_user()
    service, _, tabela_repo, _, _, _ = _build_service()
    tabela = await service.criar_tabela_progressiva(admin, {"codigo": "INSS_2026", "nome": "INSS 2026"})

    with pytest.raises(DomainError, match="ao menos uma faixa"):
        await service.ativar_tabela_progressiva(admin, tabela.id, "Publicar")

    with pytest.raises(DomainError, match="sobrepor"):
        await service.substituir_faixas_tabela(
            admin,
            tabela.id,
            [
                {"ordem": 1, "valor_inicial": Decimal("0.00"), "valor_final": Decimal("2000.00"), "aliquota": Decimal("7.50")},
                {"ordem": 2, "valor_inicial": Decimal("1500.00"), "valor_final": Decimal("3000.00"), "aliquota": Decimal("9.00")},
            ],
        )

    await service.substituir_faixas_tabela(
        admin,
        tabela.id,
        [{"ordem": 1, "valor_inicial": Decimal("0.00"), "valor_final": None, "aliquota": Decimal("11.00")}],
    )
    activated = await service.ativar_tabela_progressiva(admin, tabela.id, "Publicar")
    tabela_repo.used_active_ids.add(tabela.id)

    assert activated.status == StatusRegraEncargo.ATIVA
    with pytest.raises(DomainError, match="ativa"):
        await service.atualizar_tabela_progressiva(admin, tabela.id, {"nome": "Novo nome"})
