"""
ArkyModelRouter — selects the appropriate Gemini model per request complexity.
Model IDs are configured via environment variables, never hardcoded.
"""
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ModelSelection:
    model_id: str
    family: str
    reason: str


# Modules and intent patterns that require the complex model
_COMPLEX_MODULES = frozenset({"financeiro", "rh"})
_COMPLEX_INTENT_HINTS = frozenset({
    "analyze", "explain", "summary", "relatorio", "report",
    "update_obra_status", "create_obra",
})


class ArkyModelRouter:
    def select(
        self,
        message: str,
        module: str | None,
        has_screenshot: bool,
        intent_hint: str | None,
    ) -> ModelSelection:
        if has_screenshot:
            return ModelSelection(
                model_id=settings.arky_complex_model,
                family="gemini-complex",
                reason="screenshot requires multimodal model",
            )

        if module and module.lower() in _COMPLEX_MODULES:
            return ModelSelection(
                model_id=settings.arky_complex_model,
                family="gemini-complex",
                reason=f"sensitive module: {module}",
            )

        if intent_hint and intent_hint.lower() in _COMPLEX_INTENT_HINTS:
            return ModelSelection(
                model_id=settings.arky_complex_model,
                family="gemini-complex",
                reason=f"complex intent: {intent_hint}",
            )

        if len(message) > 300:
            return ModelSelection(
                model_id=settings.arky_complex_model,
                family="gemini-complex",
                reason="long message requiring deeper reasoning",
            )

        return ModelSelection(
            model_id=settings.arky_simple_model,
            family="gemini-simple",
            reason="simple task",
        )
