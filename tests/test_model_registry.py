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


def test_strong_chain_leads_with_paid_strong_and_falls_back_to_free():
    chain = ModelRouter().chain_for(STRONG)
    # Tarefas complexas devem liderar com o modelo mais forte (pago), não free.
    assert chain[0] in catalog.ids_fortes()
    assert catalog.obter_spec(chain[0]).gratuito is False
    # Garante fallback gratuito ao final, conforme requisito do projeto.
    assert any(mid in catalog.ids_gratuitos() for mid in chain)
    # O fallback gratuito vem depois do(s) modelo(s) pago(s).
    first_free = next(i for i, m in enumerate(chain) if m in catalog.ids_gratuitos())
    assert first_free > 0


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
