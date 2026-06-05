"""
ModelRouter — consome o catalogo curado (model_catalog) e monta as cadeias de
fallback por PAPEL LOGICO.

Papeis:
  - "weak":   tarefas simples (parsing, classificacao, execucao). Free-first,
              depois modelos fracos pagos dentro do teto de custo.
  - "strong": tarefas complexas (planejamento, reasoning, sintese). Modelos
              fortes em ordem de preferencia, com FALLBACK final para modelos
              gratuitos — nunca fica sem resposta por custo/indisponibilidade.
  - "vision": entrada multimodal (screenshot). Modelos com visao, fortes primeiro.

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
    def _build_weak(self) -> list[str]:
        # Gratuitos primeiro (custo zero), depois fracos pagos dentro do teto.
        return _dedupe(catalog.ids_gratuitos() + catalog.ids_fracos_dentro_do_teto())

    def _build_strong(self) -> list[str]:
        # Tarefas complexas lideram com o modelo MAIS FORTE (pago), conforme
        # requisito de produto, e caem para gratuitos apenas como ultimo recurso
        # (custo/indisponibilidade). Modelos fortes gratuitos entram no bloco de
        # fallback gratuito, nunca a frente dos pagos.
        fortes_pagos = [
            s.id
            for s in catalog.specs_por_categoria(catalog.Categoria.FORTE)
            if not s.gratuito
        ]
        return _dedupe(fortes_pagos + catalog.ids_gratuitos())

    def _build_vision(self) -> list[str]:
        chain = catalog.ids_com_vision()
        # Sem modelo de visao no catalogo? cai para a cadeia forte (best-effort).
        return _dedupe(chain) if chain else self._build_strong()
