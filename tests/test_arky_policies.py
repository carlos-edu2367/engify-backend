"""Unit tests for ArkyPolicyEngine — deny-by-default security."""
import pytest

from app.application.services.arky.policies import ArkyPolicyEngine
from app.domain.entities.user import Roles, User
from app.domain.entities.team import Team
from uuid import uuid4


def _make_user(role: Roles) -> User:
    team = object.__new__(Team)
    team.id = uuid4()
    team.title = "Test Team"
    team.expiration_date = None

    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Test User"
    user.email = "test@example.com"
    user.senha_hash = "hash"
    user.role = role
    user.team = team
    user.cpf = None
    return user


@pytest.fixture
def engine():
    return ArkyPolicyEngine()


class TestDenyByDefault:
    def test_unknown_tool_denied(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("nonexistent_tool", user) is False

    def test_empty_tool_name_denied(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("", user) is False


class TestObrasTools:
    def test_admin_can_read_obras(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("obras_get_detail", user) is True
        assert engine.is_tool_allowed("obras_list", user) is True

    def test_engenheiro_can_read_obras(self, engine):
        user = _make_user(Roles.ENGENHEIRO)
        assert engine.is_tool_allowed("obras_get_detail", user) is True

    def test_cliente_can_read_obras(self, engine):
        user = _make_user(Roles.CLIENTE)
        assert engine.is_tool_allowed("obras_get_detail", user) is True

    def test_funcionario_cannot_read_obras(self, engine):
        user = _make_user(Roles.FUNCIONARIO)
        assert engine.is_tool_allowed("obras_get_detail", user) is False

    def test_admin_can_prepare_create_obra(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("obras_prepare_create", user) is True

    def test_engenheiro_can_prepare_create_obra(self, engine):
        user = _make_user(Roles.ENGENHEIRO)
        assert engine.is_tool_allowed("obras_prepare_create", user) is True

    def test_financeiro_cannot_prepare_create_obra(self, engine):
        user = _make_user(Roles.FINANCEIRO)
        assert engine.is_tool_allowed("obras_prepare_create", user) is False

    def test_cliente_cannot_prepare_create_obra(self, engine):
        user = _make_user(Roles.CLIENTE)
        assert engine.is_tool_allowed("obras_prepare_create", user) is False


class TestFinanceiroTools:
    def test_admin_can_access_financeiro(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("financeiro_get_fluxo_caixa", user, "financeiro") is True

    def test_financeiro_role_can_access(self, engine):
        user = _make_user(Roles.FINANCEIRO)
        assert engine.is_tool_allowed("financeiro_get_fluxo_caixa", user, "financeiro") is True

    def test_engenheiro_cannot_access_financeiro(self, engine):
        user = _make_user(Roles.ENGENHEIRO)
        assert engine.is_tool_allowed("financeiro_get_fluxo_caixa", user, "financeiro") is False

    def test_financeiro_tool_blocked_outside_financeiro_module(self, engine):
        """Tool is module-scoped; blocked if module is wrong."""
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("financeiro_get_fluxo_caixa", user, "obras") is False
        assert engine.is_tool_allowed("financeiro_get_fluxo_caixa", user, None) is False


class TestRhTools:
    def test_funcionario_can_access_me_resumo(self, engine):
        user = _make_user(Roles.FUNCIONARIO)
        assert engine.is_tool_allowed("rh_get_me_resumo", user, "rh") is True

    def test_admin_cannot_access_me_resumo(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("rh_get_me_resumo", user, "rh") is False

    def test_admin_can_access_rh_dashboard(self, engine):
        user = _make_user(Roles.ADMIN)
        assert engine.is_tool_allowed("rh_get_dashboard", user, "rh") is True

    def test_funcionario_cannot_access_rh_dashboard(self, engine):
        user = _make_user(Roles.FUNCIONARIO)
        assert engine.is_tool_allowed("rh_get_dashboard", user, "rh") is False


class TestGetAllowedTools:
    def test_admin_gets_tools_for_financeiro_module(self, engine):
        user = _make_user(Roles.ADMIN)
        tools = engine.get_allowed_tools(user, "financeiro")
        names = [t.name for t in tools]
        assert "financeiro_get_fluxo_caixa" in names
        assert "obras_get_detail" in names

    def test_cliente_gets_limited_tools(self, engine):
        user = _make_user(Roles.CLIENTE)
        tools = engine.get_allowed_tools(user, "obras")
        names = [t.name for t in tools]
        assert "obras_get_detail" in names
        assert "obras_prepare_create" not in names
        assert "financeiro_get_fluxo_caixa" not in names
