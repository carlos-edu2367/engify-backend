"""Unit tests for ModelRouter — fallback chain assembly per logical role."""
from app.infra.ai import model_catalog as catalog
from app.infra.ai.model_registry import STRONG, VISION, WEAK, ModelRouter


def test_weak_chain_is_free_first():
    chain = ModelRouter().chain_for(WEAK)
    assert chain
    free = catalog.ids_gratuitos()
    # Todos os gratuitos aparecem antes de qualquer modelo pago na cadeia fraca.
    first_paid = next(
        (i for i, mid in enumerate(chain) if mid not in free), len(chain)
    )
    free_positions = [i for i, mid in enumerate(chain) if mid in free]
    assert all(pos < first_paid for pos in free_positions)


def test_strong_chain_is_free_first_and_same_as_weak():
    # Cost-control: Arky e simples, a cadeia "forte" tambem lidera com gratuito
    # e usa a MESMA escada free-first do texto (Gemini apenas no fim).
    strong = ModelRouter().chain_for(STRONG)
    weak = ModelRouter().chain_for(WEAK)
    assert strong == weak
    assert catalog.obter_spec(strong[0]).gratuito is True
    # Gemini (caro) e o ultimo recurso, nunca a frente dos gratuitos/baratos.
    gemini_positions = [i for i, m in enumerate(strong) if m.startswith("google/gemini-")]
    free_positions = [i for i, m in enumerate(strong) if m in catalog.ids_gratuitos()]
    assert gemini_positions, "a escada deve terminar com Gemini como ultimo recurso"
    assert max(free_positions) < min(gemini_positions)


def test_gemini_is_last_resort_in_text_and_vision():
    router = ModelRouter()
    for role in (WEAK, STRONG, VISION):
        chain = router.chain_for(role)
        gemini = [m for m in chain if m.startswith("google/gemini-")]
        if gemini:
            # Nenhum Gemini antes de algum modelo nao-Gemini (gratuito/barato).
            first_gemini = next(i for i, m in enumerate(chain) if m.startswith("google/gemini-"))
            assert first_gemini > 0
            # O Gemini mais caro (3.5-flash) e o ULTIMO da cadeia.
            assert chain[-1] == "google/gemini-3.5-flash"


def test_vision_chain_only_has_vision_models_when_catalog_has_them():
    chain = ModelRouter().chain_for(VISION)
    assert chain
    vision_ids = set(catalog.ids_com_vision())
    if vision_ids:
        assert all(mid in vision_ids for mid in chain)


def test_chains_have_no_duplicates():
    router = ModelRouter()
    for role in (WEAK, STRONG, VISION):
        chain = router.chain_for(role)
        assert len(chain) == len(set(chain))


def test_unknown_role_defaults_to_weak():
    router = ModelRouter()
    assert router.chain_for("banana") == router.chain_for(WEAK)


def test_env_override_replaces_chain_entirely():
    router = ModelRouter(overrides={"strong": ["acme/new-model", "acme/backup"]})
    assert router.chain_for(STRONG) == ["acme/new-model", "acme/backup"]
    # Override de um papel não afeta os outros.
    assert router.chain_for(WEAK) == ModelRouter().chain_for(WEAK)


def test_chain_for_returns_a_copy():
    router = ModelRouter()
    chain = router.chain_for(WEAK)
    chain.append("mutated")
    assert "mutated" not in router.chain_for(WEAK)
