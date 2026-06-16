import pytest
from uuid import uuid4

from app.domain.entities.identities import CPF
from app.domain.entities.team import Team, Plans
from app.domain.entities.user import Roles, User
from fastapi import HTTPException
from app.http.dependencies.auth import require_admin, require_funcionario, require_invite_actor, require_manager, require_rh_admin


def _make_user(role: Roles) -> User:
    team = object.__new__(Team)
    team.id = uuid4()
    team.title = "Engify"
    team.cnpj = "12345678000195"
    team.plan = Plans.PRO
    from datetime import datetime, timezone, timedelta
    team.expiration_date = datetime.now(timezone.utc) + timedelta(days=30)

    cpf = CPF("52998224725")
    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Carlos"
    user.email = "carlos@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = team
    user.cpf = cpf
    return user


def test_require_rh_admin_allows_admin():
    user = _make_user(Roles.ADMIN)

    assert require_rh_admin(user) is user


def test_require_rh_admin_allows_financeiro():
    user = _make_user(Roles.FINANCEIRO)

    assert require_rh_admin(user) is user


def test_require_manager_allows_financeiro():
    user = _make_user(Roles.FINANCEIRO)

    assert require_manager(user) is user


def test_require_rh_admin_blocks_funcionario():
    user = _make_user(Roles.FUNCIONARIO)

    with pytest.raises(Exception):
        require_rh_admin(user)


def test_require_funcionario_allows_funcionario():
    user = _make_user(Roles.FUNCIONARIO)

    assert require_funcionario(user) is user


@pytest.mark.parametrize("role", [Roles.ADMIN, Roles.FINANCEIRO, Roles.CLIENTE])
def test_require_funcionario_blocks_other_roles(role: Roles):
    user = _make_user(role)

    with pytest.raises(Exception):
        require_funcionario(user)


def test_require_invite_actor_allows_admin():
    user = _make_user(Roles.ADMIN)
    assert require_invite_actor(user) is user


def test_require_invite_actor_allows_financeiro():
    user = _make_user(Roles.FINANCEIRO)
    assert require_invite_actor(user) is user


@pytest.mark.parametrize("role", [Roles.ENGENHEIRO, Roles.CLIENTE, Roles.FUNCIONARIO])
def test_require_invite_actor_blocks_other_roles(role: Roles):
    user = _make_user(role)
    with pytest.raises(HTTPException) as exc:
        require_invite_actor(user)
    assert exc.value.status_code == 403


def test_require_admin_allows_admin():
    user = _make_user(Roles.ADMIN)
    assert require_admin(user) is user


@pytest.mark.parametrize("role", [
    Roles.ENGENHEIRO,
    Roles.FINANCEIRO,
    Roles.CLIENTE,
    Roles.FUNCIONARIO,
    Roles.SUPER_ADMIN,
])
def test_require_admin_blocks_other_roles(role: Roles):
    user = _make_user(role)
    with pytest.raises(HTTPException) as exc:
        require_admin(user)
    assert exc.value.status_code == 403
