"""
ModelRouter — consome o catalogo curado (model_catalog) e monta as cadeias de
fallback por PAPEL LOGICO.

Estrategia free-first (cost-control): Arky e um assistente operacional simples;
TODAS as cadeias lideram com Gemma 4 GRATUITO e escalam por modelos pagos baratos
(Gemma 4 pago -> DeepSeek -> Qwen), deixando o Gemini (caro) como ULTIMO recurso.

Papeis:
  - "weak":   tarefas simples (parsing, classificacao, execucao). Cadeia free-first.
  - "strong": tarefas complexas. MESMA cadeia free-first (custo acima de tudo);
              o Gemini so e alcancado se todos os anteriores falharem.
  - "vision": entrada multimodal (screenshot). Modelos COM visao, tambem free-first
              (Gemma 4 gratuito suporta imagem); escala p/ Qwen e por fim Gemini.

Cada cadeia pode ser SOBRESCRITA por env var (lista separada por virgula), sem
deploy de codigo (ver app.core.config.Settings.openrouter_model_overrides):
  - OPENROUTER_MODELS_WEAK
  - OPENROUTER_MODELS_STRONG
  - OPENROUTER_MODELS_VISION

Ids no override NAO precisam existir no catalogo — isso permite adotar um modelo
recem-lancado apenas mexendo no ambiente.
"""
from __future__ import annotations

from app.infra.ai import model_catalog as catalog

WEAK = "weak"
STRONG = "strong"
VISION = "vision"

ROLES = (WEAK, STRONG, VISION)


def _dedupe(ids: list[str]) -> list[str]:
    """Remove duplicatas preservando a ordem (preferido -> ultimo)."""
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


class ModelRouter:
    """Monta e serve cadeias de fallback por papel logico.

    As cadeias sao calculadas uma vez na construcao (catalogo e estatico) e
    podem ser substituidas integralmente por overrides de ambiente.
    """

    def __init__(self, overrides: dict[str, list[str]] | None = None) -> None:
        self._overrides = {k.lower(): v for k, v in (overrides or {}).items() if v}
        self._chains: dict[str, list[str]] = {
            WEAK: self._build_weak(),
            STRONG: self._build_strong(),
            VISION: self._build_vision(),
        }

    def chain_for(self, role: str) -> list[str]:
        """Cadeia de fallback (copia) para um papel. Papel desconhecido -> weak."""
        role = (role or WEAK).lower()
        if role in self._overrides:
            return list(self._overrides[role])
        return list(self._chains.get(role, self._chains[WEAK]))

    def all_chains(self) -> dict[str, list[str]]:
        return {role: self.chain_for(role) for role in ROLES}

    # -- construcao a partir do catalogo --------------------------------------
    def _canonical_text_chain(self) -> list[str]:
        """Cadeia unica free-first para TODO fluxo de texto.

        Segue a ordem do catalogo (que ja e gratuito -> pago barato -> Gemini),
        materializando o requisito de produto: Gemma 4 gratuito primeiro, depois
        Gemma 4 pago, DeepSeek, Qwen e SO em ultimo caso Gemini (caro). DeepSeek
        (sem visao) participa de texto normalmente.
        """
        return _dedupe([s.id for s in catalog.CATALOGO])

    def _build_weak(self) -> list[str]:
        # Arky e um assistente simples: a tarefa "fraca" usa a mesma cadeia
        # free-first do texto. Nunca lidera com modelo pago.
        return self._canonical_text_chain()

    def _build_strong(self) -> list[str]:
        # Tarefas "fortes" tambem lideram com gratuito e escalam pela MESMA
        # cadeia; o Gemini (caro) continua sendo o ultimo recurso. Cost-control
        # acima de tudo, conforme requisito.
        return self._canonical_text_chain()

    def _build_vision(self) -> list[str]:
        # Visao tambem e free-first: Gemma 4 gratuito suporta imagem. So escala
        # para Qwen/Gemini quando necessario. Exclui modelos sem visao (DeepSeek).
        chain = catalog.ids_com_vision()
        return _dedupe(chain) if chain else self._canonical_text_chain()
