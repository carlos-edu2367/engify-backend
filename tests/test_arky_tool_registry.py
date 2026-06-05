"""Unit tests for ArkyToolRegistry — allowlist enforcement."""
import pytest

from app.application.services.arky.tool_registry import ArkyToolRegistry


@pytest.fixture
def registry():
    return ArkyToolRegistry()


class TestGetDeclaration:
    def test_known_tool_returns_declaration(self, registry):
        decl = registry.get_declaration("obras_get_detail")
        assert decl is not None
        assert decl.name == "obras_get_detail"
        assert decl.description
        assert decl.parameters

    def test_unknown_tool_returns_none(self, registry):
        assert registry.get_declaration("nonexistent_tool") is None

    def test_empty_string_returns_none(self, registry):
        assert registry.get_declaration("") is None

    def test_sql_injection_attempt_returns_none(self, registry):
        assert registry.get_declaration("obras_get_detail; DROP TABLE obras;") is None


class TestGetDeclarationsFor:
    def test_returns_only_registered_tools(self, registry):
        names = ["obras_get_detail", "obras_list", "nonexistent_tool", ""]
        decls = registry.get_declarations_for(names)
        returned_names = {d.name for d in decls}
        assert "obras_get_detail" in returned_names
        assert "obras_list" in returned_names
        assert "nonexistent_tool" not in returned_names

    def test_empty_list_returns_empty(self, registry):
        assert registry.get_declarations_for([]) == []

    def test_all_unknown_returns_empty(self, registry):
        assert registry.get_declarations_for(["bad_tool", "hack_attempt"]) == []


class TestDeclaredToolsAreComplete:
    """All declared tools must have name, description, and parameters."""

    EXPECTED_TOOLS = [
        "obras_get_detail",
        "obras_list",
        "items_list_by_obra",
        "notificacoes_list",
        "financeiro_get_fluxo_caixa",
        "rh_get_me_resumo",
        "rh_get_dashboard",
        "obras_prepare_create",
        "obras_prepare_update_status",
        "items_prepare_create",
        "notificacoes_prepare_send",
        "financeiro_pagamentos_overview",
        "financeiro_buscar_pagamentos",
        "diaristas_list",
        "financeiro_prepare_pagamentos",
    ]

    def test_prepare_pagamentos_schema_supports_list(self, registry):
        decl = registry.get_declaration("financeiro_prepare_pagamentos")
        props = decl.parameters["properties"]
        assert props["pagamentos"]["type"] == "ARRAY"
        item_props = props["pagamentos"]["items"]["properties"]
        # Classe enum must be derived from the domain MovClass values.
        from app.domain.entities.financeiro import MovClass
        assert set(item_props["classe"]["enum"]) == {c.value for c in MovClass}
        assert set(props["pagamentos"]["items"]["required"]) == {"title", "valor", "classe"}

    def test_all_expected_tools_exist(self, registry):
        for tool_name in self.EXPECTED_TOOLS:
            decl = registry.get_declaration(tool_name)
            assert decl is not None, f"Tool '{tool_name}' not found in registry"

    def test_all_tools_have_parameters_schema(self, registry):
        for tool_name in self.EXPECTED_TOOLS:
            decl = registry.get_declaration(tool_name)
            assert decl.parameters is not None, f"Tool '{tool_name}' missing parameters"
            assert "type" in decl.parameters, f"Tool '{tool_name}' parameters missing 'type'"

    def test_all_tools_have_non_empty_description(self, registry):
        for tool_name in self.EXPECTED_TOOLS:
            decl = registry.get_declaration(tool_name)
            assert decl.description.strip(), f"Tool '{tool_name}' has empty description"
