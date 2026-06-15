from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.rh_encargo_service import RhEncargoService
from app.domain.entities.money import Money
from app.domain.entities.rh import Beneficio, StatusBeneficio
from app.domain.entities.user import Roles, User


class _FakeUow:
    async def commit(self):
        pass


class _FakeAudit:
    async def save(self, log):
        return log


class _FakeBeneficioRepo:
    def __init__(self):
        self.items = {}

    async def get_by_id(self, id, team_id):
        return self.items[id]

    async def get_active_by_nome(self, team_id, nome):
        return None

    async def save(self, b):
        self.items[b.id] = b
        return b


class _FakeVinculoRepo:
    def __init__(self):
        self.items = []

    async def list_by_beneficio(self, team_id, beneficio_id):
        return [v for v in self.items if v.beneficio_id == beneficio_id and not v.is_deleted]

    async def get_vinculo(self, team_id, beneficio_id, funcionario_id):
        for v in self.items:
            if v.beneficio_id == beneficio_id and v.funcionario_id == funcionario_id and not v.is_deleted:
                return v
        return None

    async def save(self, v):
        self.items.append(v)
        return v


def _user():
    team = type("T", (), {"id": uuid4()})()
    u = object.__new__(User)
    u.id = uuid4()
    u.role = Roles.ADMIN
    u.team = team
    return u


def _service(beneficio_repo, vinculo_repo):
    return RhEncargoService(
        regra_repo=None,
        tabela_repo=None,
        audit_repo=_FakeAudit(),
        uow=_FakeUow(),
        beneficio_repo=beneficio_repo,
        beneficio_funcionario_repo=vinculo_repo,
    )


@pytest.mark.asyncio
async def test_atualizar_beneficio_salva_valor_dia():
    user = _user()
    repo = _FakeBeneficioRepo()
    b = Beneficio(team_id=user.team.id, nome="VR")
    repo.items[b.id] = b
    svc = _service(repo, _FakeVinculoRepo())
    saved = await svc.atualizar_beneficio(user, b.id, {"valor_dia": "25.00"})
    assert saved.valor_dia == Money(Decimal("25.00"))


@pytest.mark.asyncio
async def test_atribuir_funcionario_cria_vinculo():
    user = _user()
    repo = _FakeBeneficioRepo()
    b = Beneficio(team_id=user.team.id, nome="VR")
    repo.items[b.id] = b
    vinc = _FakeVinculoRepo()
    svc = _service(repo, vinc)
    func_id = uuid4()
    await svc.atribuir_funcionario(user, b.id, func_id)
    assert vinc.items[0].funcionario_id == func_id
    assert vinc.items[0].status == StatusBeneficio.ATIVO
