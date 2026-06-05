"""Unit tests for ArkyModelRouter — role-based model-chain selection logic."""
import pytest

from app.application.services.arky.model_router import ArkyModelRouter
from app.infra.ai.model_registry import STRONG, VISION, WEAK


@pytest.fixture
def router():
    return ArkyModelRouter()


def _assert_chain(sel, role):
    assert sel.role == role
    assert sel.chain, "a cadeia de fallback não pode ser vazia"
    assert sel.model_id == sel.chain[0]
    assert sel.family == f"openrouter-{role}"
    assert sel.reason


class TestScreenshotAlwaysVision:
    def test_screenshot_selects_vision_chain(self, router):
        sel = router.select(message="ajuda", module="obras", has_screenshot=True, intent_hint=None)
        _assert_chain(sel, VISION)

    def test_screenshot_overrides_simple_module(self, router):
        sel = router.select(message="ok", module="geral", has_screenshot=True, intent_hint=None)
        _assert_chain(sel, VISION)


class TestSensitiveModulesStrong:
    def test_financeiro_selects_strong(self, router):
        sel = router.select(message="me explique", module="financeiro", has_screenshot=False, intent_hint=None)
        _assert_chain(sel, STRONG)

    def test_rh_selects_strong(self, router):
        sel = router.select(message="me explique", module="rh", has_screenshot=False, intent_hint=None)
        _assert_chain(sel, STRONG)


class TestSimpleTasksWeak:
    def test_short_message_obras_uses_weak(self, router):
        sel = router.select(message="listar obras", module="obras", has_screenshot=False, intent_hint=None)
        _assert_chain(sel, WEAK)

    def test_no_module_short_uses_weak(self, router):
        sel = router.select(message="oi", module=None, has_screenshot=False, intent_hint=None)
        _assert_chain(sel, WEAK)


class TestComplexIntentHints:
    def test_create_obra_intent_uses_strong(self, router):
        sel = router.select(message="crie uma obra", module="obras", has_screenshot=False, intent_hint="create_obra")
        _assert_chain(sel, STRONG)

    def test_report_intent_uses_strong(self, router):
        sel = router.select(message="gere relatorio", module="financeiro", has_screenshot=False, intent_hint="relatorio")
        _assert_chain(sel, STRONG)

    def test_unknown_intent_falls_through_to_length(self, router):
        sel = router.select(message="oi", module="obras", has_screenshot=False, intent_hint="unknown_intent_xyz")
        _assert_chain(sel, WEAK)


class TestLongMessageStrong:
    def test_message_over_300_chars_uses_strong(self, router):
        long = "x" * 301
        sel = router.select(message=long, module="obras", has_screenshot=False, intent_hint=None)
        _assert_chain(sel, STRONG)

    def test_message_exactly_300_uses_weak(self, router):
        msg = "x" * 300
        sel = router.select(message=msg, module="obras", has_screenshot=False, intent_hint=None)
        _assert_chain(sel, WEAK)


class TestRegistryOverridesAreHonored:
    def test_env_override_replaces_weak_chain(self):
        from app.infra.ai.model_registry import ModelRouter
        router = ArkyModelRouter(
            registry=ModelRouter(overrides={"weak": ["my/custom-free-model"]})
        )
        sel = router.select(message="oi", module=None, has_screenshot=False, intent_hint=None)
        assert sel.chain == ["my/custom-free-model"]
