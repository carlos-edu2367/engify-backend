"""Unit tests for ArkyModelRouter — model selection logic."""
import pytest

from app.application.services.arky.model_router import ArkyModelRouter
from app.core.config import settings


@pytest.fixture
def router():
    return ArkyModelRouter()


class TestScreenshotAlwaysComplex:
    def test_screenshot_selects_complex_model(self, router):
        sel = router.select(message="ajuda", module="obras", has_screenshot=True, intent_hint=None)
        assert sel.model_id == settings.arky_complex_model

    def test_screenshot_overrides_simple_module(self, router):
        sel = router.select(message="ok", module="geral", has_screenshot=True, intent_hint=None)
        assert sel.model_id == settings.arky_complex_model


class TestSensitiveModulesComplex:
    def test_financeiro_selects_complex(self, router):
        sel = router.select(message="me explique", module="financeiro", has_screenshot=False, intent_hint=None)
        assert sel.model_id == settings.arky_complex_model

    def test_rh_selects_complex(self, router):
        sel = router.select(message="me explique", module="rh", has_screenshot=False, intent_hint=None)
        assert sel.model_id == settings.arky_complex_model


class TestSimpleTasksSimpleModel:
    def test_short_message_obras_uses_simple(self, router):
        sel = router.select(message="listar obras", module="obras", has_screenshot=False, intent_hint=None)
        assert sel.model_id == settings.arky_simple_model

    def test_no_module_short_uses_simple(self, router):
        sel = router.select(message="oi", module=None, has_screenshot=False, intent_hint=None)
        assert sel.model_id == settings.arky_simple_model


class TestComplexIntentHints:
    def test_create_obra_intent_uses_complex(self, router):
        sel = router.select(message="crie uma obra", module="obras", has_screenshot=False, intent_hint="create_obra")
        assert sel.model_id == settings.arky_complex_model

    def test_report_intent_uses_complex(self, router):
        sel = router.select(message="gere relatorio", module="financeiro", has_screenshot=False, intent_hint="relatorio")
        assert sel.model_id == settings.arky_complex_model

    def test_unknown_intent_falls_through_to_length(self, router):
        sel = router.select(message="oi", module="obras", has_screenshot=False, intent_hint="unknown_intent_xyz")
        assert sel.model_id == settings.arky_simple_model


class TestLongMessageComplex:
    def test_message_over_300_chars_uses_complex(self, router):
        long = "x" * 301
        sel = router.select(message=long, module="obras", has_screenshot=False, intent_hint=None)
        assert sel.model_id == settings.arky_complex_model

    def test_message_exactly_300_uses_simple(self, router):
        msg = "x" * 300
        sel = router.select(message=msg, module="obras", has_screenshot=False, intent_hint=None)
        assert sel.model_id == settings.arky_simple_model


class TestSelectionHasReason:
    def test_selection_includes_reason(self, router):
        sel = router.select(message="oi", module="financeiro", has_screenshot=False, intent_hint=None)
        assert sel.reason
        assert sel.family
