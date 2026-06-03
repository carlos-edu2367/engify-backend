"""Unit tests for ArkyContextBuilder — sanitization and permission summary."""
import pytest
from uuid import uuid4

from app.application.services.arky.context_builder import ArkyContextBuilder
from app.domain.entities.user import Roles, User
from app.domain.entities.team import Team


def _make_user(role: Roles) -> User:
    team = object.__new__(Team)
    team.id = uuid4()
    team.title = "Test Team"

    user = object.__new__(User)
    user.id = uuid4()
    user.nome = "Test"
    user.email = "t@example.com"
    user.senha_hash = "h"
    user.role = role
    user.team = team
    user.cpf = None
    return user


@pytest.fixture
def builder():
    return ArkyContextBuilder()


class TestSanitization:
    def test_message_truncated_at_2000(self, builder):
        user = _make_user(Roles.ADMIN)
        long_msg = "x" * 3000
        result = builder.sanitize_message(long_msg)
        assert len(result) == 2000

    def test_message_stripped(self, builder):
        result = builder.sanitize_message("  hello  ")
        assert result == "hello"

    def test_route_truncated(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(
            user=user,
            screen_data={"route": "x" * 300, "path": "/", "title": "T", "module": "obras"},
            selection_data=None,
            ui_state_data=None,
            has_screenshot=False,
        )
        assert len(ctx.route) <= 200

    def test_filters_blocks_sensitive_keys(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(
            user=user,
            screen_data=None,
            selection_data=None,
            ui_state_data={"filters": {"status": "all", "cpf": "123", "pix": "key"}},
            has_screenshot=False,
        )
        # Sensitive keys must be removed from filters
        if ctx.filters:
            assert "cpf" not in ctx.filters
            assert "pix" not in ctx.filters
            assert "status" in ctx.filters


class TestScreenshotBlocking:
    def test_screenshot_blocked_in_financeiro(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(
            user=user,
            screen_data={"route": "/financeiro", "module": "financeiro"},
            selection_data=None,
            ui_state_data=None,
            has_screenshot=True,
        )
        assert ctx.screenshot_blocked is True
        assert ctx.screenshot_included is False

    def test_screenshot_blocked_in_rh(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(
            user=user,
            screen_data={"route": "/rh", "module": "rh"},
            selection_data=None,
            ui_state_data=None,
            has_screenshot=True,
        )
        assert ctx.screenshot_blocked is True

    def test_screenshot_allowed_in_obras(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(
            user=user,
            screen_data={"route": "/obras", "module": "obras"},
            selection_data=None,
            ui_state_data=None,
            has_screenshot=True,
        )
        assert ctx.screenshot_blocked is False
        assert ctx.screenshot_included is True

    def test_no_screenshot_allowed_when_not_provided(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(
            user=user,
            screen_data={"route": "/obras", "module": "obras"},
            selection_data=None,
            ui_state_data=None,
            has_screenshot=False,
        )
        assert ctx.screenshot_included is False


class TestPermissionSummary:
    def test_admin_has_all_permissions(self, builder):
        user = _make_user(Roles.ADMIN)
        ctx = builder.build(user=user, screen_data=None, selection_data=None, ui_state_data=None, has_screenshot=False)
        p = ctx.permission_summary
        assert p["can_read_obras"] is True
        assert p["can_edit_obras"] is True
        assert p["can_read_financeiro"] is True
        assert p["can_read_rh_admin"] is True
        assert p["can_read_rh_me"] is False

    def test_funcionario_has_limited_permissions(self, builder):
        user = _make_user(Roles.FUNCIONARIO)
        ctx = builder.build(user=user, screen_data=None, selection_data=None, ui_state_data=None, has_screenshot=False)
        p = ctx.permission_summary
        assert p["can_read_obras"] is False
        assert p["can_read_financeiro"] is False
        assert p["can_read_rh_me"] is True

    def test_cliente_can_read_obras_only(self, builder):
        user = _make_user(Roles.CLIENTE)
        ctx = builder.build(user=user, screen_data=None, selection_data=None, ui_state_data=None, has_screenshot=False)
        p = ctx.permission_summary
        assert p["can_read_obras"] is True
        assert p["can_edit_obras"] is False
        assert p["can_read_financeiro"] is False
