"""Tests for safe static knowledge exposed to Arky."""

from app.application.services.arky.knowledge import ArkyKnowledgeProvider


def test_financeiro_knowledge_explains_module_without_granting_access():
    provider = ArkyKnowledgeProvider()

    text = provider.build_context(
        module="financeiro",
        permission_summary={"can_read_financeiro": False, "role": "engenheiro"},
    )

    assert "Financeiro" in text
    assert "movimentacoes" in text
    assert "sem permissao" in text
    assert "Pix completo" in text


def test_rh_knowledge_distinguishes_admin_and_meu_rh_permissions():
    provider = ArkyKnowledgeProvider()

    text = provider.build_context(
        module="rh",
        permission_summary={
            "can_read_rh_admin": False,
            "can_read_rh_me": True,
            "role": "funcionario",
        },
    )

    assert "RH" in text
    assert "Meu RH" in text
    assert "dashboard administrativo" in text
    assert "nao deve acessar" in text


def test_general_knowledge_lists_core_modules_safely():
    provider = ArkyKnowledgeProvider()

    text = provider.build_context(module="geral", permission_summary={"role": "admin"})

    assert "Obras" in text
    assert "Financeiro" in text
    assert "RH" in text
    assert "dados dinamicos" in text
