"""
ArkyPolicyEngine — deny-by-default RBAC/ABAC policy checker.
The model never decides authorization. This module decides.
"""
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.user import Roles, User


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    allowed_roles: frozenset[Roles]
    # Modules this tool is scoped to (empty = any module)
    allowed_modules: frozenset[str] = frozenset()
    requires_confirmation: bool = False
    risk_level: str = "leitura"  # leitura | sugestao | preparacao | escrita_sensivel
    blocked_in_mvp: bool = False


# Canonical allowlist. Tools not listed here are implicitly denied.
_TOOL_POLICIES: dict[str, ToolPolicy] = {
    "obras_get_detail": ToolPolicy(
        name="obras_get_detail",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO, Roles.CLIENTE}),
        risk_level="leitura",
    ),
    "obras_list": ToolPolicy(
        name="obras_list",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO, Roles.CLIENTE}),
        risk_level="leitura",
    ),
    "items_list_by_obra": ToolPolicy(
        name="items_list_by_obra",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO, Roles.CLIENTE}),
        risk_level="leitura",
    ),
    "notificacoes_list": ToolPolicy(
        name="notificacoes_list",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO, Roles.FUNCIONARIO}),
        risk_level="leitura",
    ),
    "financeiro_get_fluxo_caixa": ToolPolicy(
        name="financeiro_get_fluxo_caixa",
        allowed_roles=frozenset({Roles.ADMIN, Roles.FINANCEIRO}),
        allowed_modules=frozenset({"financeiro"}),
        risk_level="leitura",
    ),
    "rh_get_me_resumo": ToolPolicy(
        name="rh_get_me_resumo",
        allowed_roles=frozenset({Roles.FUNCIONARIO}),
        allowed_modules=frozenset({"rh"}),
        risk_level="leitura",
    ),
    "rh_get_dashboard": ToolPolicy(
        name="rh_get_dashboard",
        allowed_roles=frozenset({Roles.ADMIN, Roles.FINANCEIRO}),
        allowed_modules=frozenset({"rh"}),
        risk_level="leitura",
    ),
    "obras_prepare_create": ToolPolicy(
        name="obras_prepare_create",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO}),
        requires_confirmation=True,
        risk_level="preparacao",
    ),
    "obras_prepare_update_status": ToolPolicy(
        name="obras_prepare_update_status",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO}),
        requires_confirmation=True,
        risk_level="preparacao",
    ),
    "items_prepare_create": ToolPolicy(
        name="items_prepare_create",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO}),
        requires_confirmation=True,
        risk_level="preparacao",
    ),
    "notificacoes_prepare_send": ToolPolicy(
        name="notificacoes_prepare_send",
        allowed_roles=frozenset({Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO}),
        requires_confirmation=True,
        risk_level="preparacao",
    ),
}


class ArkyPolicyEngine:
    def is_tool_allowed(
        self,
        tool_name: str,
        user: User,
        current_module: str | None = None,
    ) -> bool:
        policy = _TOOL_POLICIES.get(tool_name)
        if policy is None:
            return False
        if policy.blocked_in_mvp:
            return False
        if user.role not in policy.allowed_roles:
            return False
        if policy.allowed_modules and current_module not in policy.allowed_modules:
            return False
        return True

    def get_allowed_tools(
        self,
        user: User,
        current_module: str | None = None,
    ) -> list[ToolPolicy]:
        return [
            p
            for p in _TOOL_POLICIES.values()
            if self.is_tool_allowed(p.name, user, current_module)
        ]

    def get_policy(self, tool_name: str) -> ToolPolicy | None:
        return _TOOL_POLICIES.get(tool_name)
