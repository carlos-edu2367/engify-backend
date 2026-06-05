"""
Catalogo curado de modelos OpenRouter.

Fonte unica de verdade sobre QUAIS modelos existem e suas caracteristicas:
preco, categoria (forte/fraco), suporte a tools, suporte a visao, qualidade em
PT-BR e janela de contexto.

O `ModelRouter` (model_registry.py) consome este catalogo para montar as cadeias
de fallback por papel logico. Trocar/adicionar/remover modelo = editar este
arquivo ou sobrepor via env var — nunca mexer em logica.

Precos sao em USD por MILHAO de tokens (entrada e saida separados), para casar
com o formato de `pricing` do OpenRouter (`/api/v1/models`). O teto do projeto e
sobre a SOMA input+output: <= $2.00 / milhao para modelos fracos.

NOTA DE VERIFICACAO: os ids/precos abaixo sao um default sensato. Eles NAO foram
validados contra a API publica do OpenRouter nesta sessao — precos e
disponibilidade mudam. Ajuste por env var (OPENROUTER_MODELS_*) sem deploy de
codigo, ou edite este catalogo, validando contra `GET /api/v1/models`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Categoria(str, Enum):
    """Categoria de capacidade/custo do modelo."""

    FRACO = "fraco"   # execucao, parsing, classificacao, extracao, agentes secundarios
    FORTE = "forte"   # planejamento, reasoning, validacao, sintese complexa


# Teto de custo do projeto (USD por milhao de tokens, input + output somados).
# Aplica-se apenas a papeis FRACOS — papeis fortes podem exceder (decisao de produto).
TETO_CUSTO_FRACO_USD_POR_MILHAO = 2.0


@dataclass(frozen=True)
class ModelSpec:
    """Especificacao de um modelo disponivel via OpenRouter."""

    id: str
    categoria: Categoria
    preco_input_milhao: float          # USD / 1M tokens de entrada
    preco_output_milhao: float         # USD / 1M tokens de saida
    suporta_tools: bool
    suporta_vision: bool
    contexto_tokens: int
    ptbr_score: int                    # 1..5 — qualidade subjetiva em portugues
    gratuito: bool = False
    notas: str = ""

    @property
    def preco_combinado_milhao(self) -> float:
        """Soma input+output por milhao de tokens — metrica do teto do projeto."""
        return round(self.preco_input_milhao + self.preco_output_milhao, 6)

    def custo_estimado_usd(self, tokens_entrada: int, tokens_saida: int) -> float:
        """Custo estimado de uma chamada, em USD."""
        return round(
            (tokens_entrada / 1_000_000) * self.preco_input_milhao
            + (tokens_saida / 1_000_000) * self.preco_output_milhao,
            6,
        )

    def dentro_do_teto_fraco(self) -> bool:
        return self.preco_combinado_milhao <= TETO_CUSTO_FRACO_USD_POR_MILHAO


# ---------------------------------------------------------------------------
# Catalogo. Ordenado por categoria e, dentro dela, do mais barato/preferido ao
# mais caro. As cadeias de fallback padrao (model_registry) seguem esta ordem.
# ---------------------------------------------------------------------------
CATALOGO: tuple[ModelSpec, ...] = (
    # ---- GRATUITOS / FRACOS (free first) ----------------------------------
    ModelSpec(
        id="google/gemma-4-31b-it:free",
        categoria=Categoria.FORTE,
        preco_input_milhao=0.0,
        preco_output_milhao=0.0,
        suporta_tools=True,
        suporta_vision=False,
        contexto_tokens=262_144,
        ptbr_score=4,
        gratuito=True,
        notas="Gemma 4 31B gratuito; bom PT-BR e tools; 1a escolha de executor.",
    ),
    ModelSpec(
        id="google/gemma-4-26b-a4b-it:free",
        categoria=Categoria.FRACO,
        preco_input_milhao=0.0,
        preco_output_milhao=0.0,
        suporta_tools=True,
        suporta_vision=False,
        contexto_tokens=262_144,
        ptbr_score=4,
        gratuito=True,
        notas="Gemma 4 26B MoE gratuito; rapido; fallback de executor.",
    ),
    ModelSpec(
        id="inclusionai/ling-2.6-flash",
        categoria=Categoria.FRACO,
        preco_input_milhao=0.01,
        preco_output_milhao=0.03,
        suporta_tools=True,
        suporta_vision=False,
        contexto_tokens=262_144,
        ptbr_score=3,
        notas="Extremamente barato (~$0.04/M); bom para classificacao/parsing.",
    ),
    ModelSpec(
        id="qwen/qwen3.5-9b",
        categoria=Categoria.FRACO,
        preco_input_milhao=0.04,
        preco_output_milhao=0.15,
        suporta_tools=True,
        suporta_vision=False,
        contexto_tokens=262_144,
        ptbr_score=3,
        notas="Qwen 3.5 9B (~$0.19/M); tools robustas; fallback barato.",
    ),
    ModelSpec(
        id="deepseek/deepseek-v4-flash",
        categoria=Categoria.FRACO,
        preco_input_milhao=0.098,
        preco_output_milhao=0.197,
        suporta_tools=True,
        suporta_vision=False,
        contexto_tokens=1_048_576,
        ptbr_score=4,
        notas="DeepSeek V4 Flash (~$0.30/M); contexto 1M; bom custo/qualidade.",
    ),
    # ---- FORTES (podem exceder o teto) ------------------------------------
    ModelSpec(
        id="google/gemini-3.5-flash",
        categoria=Categoria.FORTE,
        preco_input_milhao=1.50,
        preco_output_milhao=9.00,
        suporta_tools=True,
        suporta_vision=True,
        contexto_tokens=1_048_576,
        ptbr_score=5,
        notas=(
            "Gemini 3.5 Flash; multimodal; 1M context; forte para "
            "planner/validator/reasoning; tool calling robusto; caro em loops massivos."
        ),
    ),
    ModelSpec(
        id="qwen/qwen3.7-plus",
        categoria=Categoria.FORTE,
        preco_input_milhao=0.40,
        preco_output_milhao=2.00,
        suporta_tools=True,
        suporta_vision=False,
        contexto_tokens=262_144,
        ptbr_score=4,
        notas="Qwen 3.7 Plus; reasoning forte; fallback de planner/validator.",
    ),
)

_POR_ID: dict[str, ModelSpec] = {spec.id: spec for spec in CATALOGO}


def obter_spec(model_id: str) -> Optional[ModelSpec]:
    """Retorna o ModelSpec de um id, ou None se nao estiver no catalogo."""
    return _POR_ID.get((model_id or "").strip())


def specs_por_categoria(categoria: Categoria) -> list[ModelSpec]:
    """Modelos de uma categoria, na ordem do catalogo (preferido -> ultimo)."""
    return [s for s in CATALOGO if s.categoria == categoria]


def ids_gratuitos() -> list[str]:
    """Ids gratuitos, na ordem do catalogo. Sempre dentro de qualquer teto."""
    return [s.id for s in CATALOGO if s.gratuito]


def ids_fracos_dentro_do_teto() -> list[str]:
    """Ids fracos (pagos ou nao) que respeitam o teto, em ordem de preferencia."""
    return [
        s.id
        for s in specs_por_categoria(Categoria.FRACO)
        if s.dentro_do_teto_fraco()
    ]


def ids_fortes() -> list[str]:
    """Ids fortes em ordem de preferencia (podem exceder o teto)."""
    return [s.id for s in specs_por_categoria(Categoria.FORTE)]


def ids_com_vision() -> list[str]:
    """Ids com suporte a visao, fortes primeiro (melhor leitura de documentos)."""
    fortes = [s.id for s in specs_por_categoria(Categoria.FORTE) if s.suporta_vision]
    fracos = [s.id for s in specs_por_categoria(Categoria.FRACO) if s.suporta_vision]
    return fortes + fracos


def suporta_vision(model_id: str) -> bool | None:
    """True/False se conhecido no catalogo; None se id desconhecido."""
    spec = obter_spec(model_id)
    return None if spec is None else spec.suporta_vision
