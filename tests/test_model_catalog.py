"""Unit tests for the curated OpenRouter model catalog."""
from app.infra.ai import model_catalog as catalog
from app.infra.ai.model_catalog import (
    TETO_CUSTO_FRACO_USD_POR_MILHAO,
    Categoria,
)


def test_catalog_is_non_empty_and_ids_unique():
    ids = [s.id for s in catalog.CATALOGO]
    assert ids
    assert len(ids) == len(set(ids)), "ids de modelo devem ser únicos"


def test_weak_within_cap_respects_project_ceiling():
    for mid in catalog.ids_fracos_dentro_do_teto():
        spec = catalog.obter_spec(mid)
        assert spec is not None
        assert spec.preco_combinado_milhao <= TETO_CUSTO_FRACO_USD_POR_MILHAO


def test_free_ids_have_zero_price_and_are_within_any_cap():
    free = catalog.ids_gratuitos()
    assert free, "deve existir ao menos um modelo gratuito"
    for mid in free:
        spec = catalog.obter_spec(mid)
        assert spec.gratuito is True
        assert spec.preco_combinado_milhao == 0.0
        assert spec.dentro_do_teto_fraco()


def test_strong_ids_are_strong_category():
    for mid in catalog.ids_fortes():
        assert catalog.obter_spec(mid).categoria == Categoria.FORTE


def test_vision_ids_support_vision():
    for mid in catalog.ids_com_vision():
        assert catalog.obter_spec(mid).suporta_vision is True


def test_suporta_vision_returns_none_for_unknown_id():
    assert catalog.suporta_vision("nonexistent/model") is None


def test_custo_estimado_matches_pricing():
    spec = catalog.obter_spec("deepseek/deepseek-v4-flash")
    # 1M de entrada + 1M de saída = input + output por milhão
    assert spec.custo_estimado_usd(1_000_000, 1_000_000) == round(
        spec.preco_input_milhao + spec.preco_output_milhao, 6
    )
