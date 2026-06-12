import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.domain.entities.identities import CPF
from app.domain.entities.team import Team, Plans
from app.domain.entities.user import Roles, User
from app.domain.errors import DomainError
from app.application.dtos.user import CreateSolicitacaoRegistro
from app.application.services.user_service import UserService


def _make_team(team_id=None) -> Team:
    team = object.__new__(Team)
    team.id = team_id or uuid4()
    team.title = "Engify"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    team.expiration_date = datetime.now(timezone.utc) + timedelta(days=30)
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


class _FakeSolicitacaoRepo:
    def __init__(self):
        self.saved = []

    async def save(self, s):
        self.saved.append(s)
        return s

    async def get_by_id(self, id):
        raise DomainError("not found")


class _FakeUOW:
    async def commit(self):
        pass


def _make_service():
    from unittest.mock import MagicMock
    svc = UserService(
        user_repo=MagicMock(),
        hash=MagicMock(),
        uow=_FakeUOW(),
        solicitacao_repo=_FakeSolicitacaoRepo(),
        team_repo=MagicMock(),
        email_port=None,
    )
    return svc


@pytest.mark.asyncio
async def test_financeiro_pode_convidar_funcionario():
    svc = _make_service()
    financeiro = _make_user(Roles.FINANCEIRO)
    dto = CreateSolicitacaoRegistro(email="func@example.com", role=Roles.FUNCIONARIO)
    result = await svc.invite_user(dto, financeiro)
    assert result.role == Roles.FUNCIONARIO
    assert result.email == "func@example.com"


@pytest.mark.asyncio
async def test_financeiro_nao_pode_convidar_admin():
    svc = _make_service()
    financeiro = _make_user(Roles.FINANCEIRO)
    dto = CreateSolicitacaoRegistro(email="admin@example.com", role=Roles.ADMIN)
    with pytest.raises(DomainError, match="Financeiro so pode convidar"):
        await svc.invite_user(dto, financeiro)


@pytest.mark.asyncio
async def test_financeiro_nao_pode_convidar_engenheiro():
    svc = _make_service()
    financeiro = _make_user(Roles.FINANCEIRO)
    dto = CreateSolicitacaoRegistro(email="eng@example.com", role=Roles.ENGENHEIRO)
    with pytest.raises(DomainError, match="Financeiro so pode convidar"):
        await svc.invite_user(dto, financeiro)


@pytest.mark.asyncio
async def test_admin_pode_convidar_qualquer_role():
    svc = _make_service()
    admin = _make_user(Roles.ADMIN)
    for role in [Roles.ENGENHEIRO, Roles.FINANCEIRO, Roles.FUNCIONARIO, Roles.CLIENTE]:
        dto = CreateSolicitacaoRegistro(email=f"{role.value}@example.com", role=role)
        result = await svc.invite_user(dto, admin)
        assert result.role == role
