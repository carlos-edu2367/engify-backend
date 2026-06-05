"""
ArkyModelRouter — classifica a complexidade de cada requisicao do Arky e devolve
a CADEIA de fallback de modelos apropriada (provider-agnostica).

A heuristica de complexidade (modulo sensivel, screenshot, intencao, tamanho da
mensagem) e regra de negocio do Arky e vive aqui. QUAIS modelos concretos
implementam cada papel (weak/strong/vision) e responsabilidade do `ModelRouter`
(model_registry.py), que consome o catalogo curado. Separacao deliberada:
trocar modelo nunca exige tocar nesta logica.
"""
from dataclasses import dataclass, field

from app.infra.ai.model_registry import ModelRouter, STRONG, VISION, WEAK


@dataclass
class ModelSelection:
    role: str                       # "weak" | "strong" | "vision"
    chain: list[str] = field(default_factory=list)  # fallback: preferido -> ultimo
    reason: str = ""

    @property
    def model_id(self) -> str:
        """Primeiro modelo da cadeia — usado na auditoria como preferencia."""
        return self.chain[0] if self.chain else ""

    @property
    def family(self) -> str:
        """Familia logica para auditoria/telemetria."""
        return f"openrouter-{self.role}"


# Modules and intent patterns that require the strong (complex) role
_COMPLEX_MODULES = frozenset({"financeiro", "rh"})
_COMPLEX_INTENT_HINTS = frozenset({
    "analyze", "explain", "summary", "relatorio", "report",
    "update_obra_status", "create_obra",
})

# Intents de extração/execução estruturada que rodam bem em modelos gratuitos
# (Gemma 4). Forçam a cadeia WEAK (free-first) MESMO em módulos sensíveis, pois
# são tarefas de parsing + tool-calling, não de raciocínio complexo. Mantém o
# requisito "free-first com fallback pago de boa qualidade" sem custo de Gemini
# em fluxos de alto volume (ex.: usuário lança vários pagamentos de uma vez).
_EXTRACTION_INTENT_HINTS = frozenset({
    "create_pagamentos", "cadastrar_pagamentos", "pagamentos_agendados",
    "agendar_pagamento", "agendar_pagamentos",
})


class ArkyModelRouter:
    def __init__(self, registry: ModelRouter | None = None) -> None:
        self._registry = registry or ModelRouter()

    def select(
        self,
        message: str,
        module: str | None,
        has_screenshot: bool,
        intent_hint: str | None,
    ) -> ModelSelection:
        if has_screenshot:
            return self._build(VISION, "screenshot requires multimodal model")

        # Extração estruturada (ex.: cadastro de pagamentos) vai para a cadeia
        # gratuita ANTES do gate de módulo sensível — Gemma 4 dá conta.
        if intent_hint and intent_hint.lower() in _EXTRACTION_INTENT_HINTS:
            return self._build(WEAK, f"structured extraction intent: {intent_hint}")

        if module and module.lower() in _COMPLEX_MODULES:
            return self._build(STRONG, f"sensitive module: {module}")

        if intent_hint and intent_hint.lower() in _COMPLEX_INTENT_HINTS:
            return self._build(STRONG, f"complex intent: {intent_hint}")

        if len(message) > 300:
            return self._build(STRONG, "long message requiring deeper reasoning")

        return self._build(WEAK, "simple task")

    def _build(self, role: str, reason: str) -> ModelSelection:
        return ModelSelection(
            role=role,
            chain=self._registry.chain_for(role),
            reason=reason,
        )
