"""
ArkyContextBuilder — sanitizes and normalizes frontend context.
Never trusts frontend as authorization source.
Backend always recalculates permissions from the authenticated user.
"""
from dataclasses import dataclass

from app.domain.entities.user import Roles, User

# Fields that must never appear in context sent to model
_BLOCKED_KEYS = frozenset({
    "cpf", "pix", "chave_pix", "senha", "password", "token", "secret",
    "api_key", "jwt", "refresh", "authorization", "download_url", "signed_url",
    "file_path", "document_url", "latitude", "longitude", "lat", "lng",
    "salario", "salary", "holerite", "folha",
})

# Modules where screenshots are blocked due to sensitivity
_SCREENSHOT_BLOCKED_MODULES = frozenset({"financeiro", "rh"})

# Max lengths to truncate context strings
_MAX_TITLE_LEN = 100
_MAX_MSG_LEN = 2000


@dataclass
class SanitizedContext:
    route: str
    path: str
    title: str
    module: str | None
    entity_type: str | None
    entity_id: str | None
    filters: dict | None
    visible_tab: str | None
    screenshot_included: bool
    screenshot_blocked: bool
    permission_summary: dict


def _sanitize_str(value, max_len: int = 200) -> str:
    if not isinstance(value, str):
        return ""
    return value[:max_len]


def _sanitize_filters(filters: dict | None) -> dict | None:
    if not filters or not isinstance(filters, dict):
        return None
    return {
        k: v for k, v in list(filters.items())[:10]
        if k.lower() not in _BLOCKED_KEYS and isinstance(k, str)
    }


def _build_permission_summary(user: User) -> dict:
    role = user.role
    return {
        "can_read_obras": role in (Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO, Roles.CLIENTE),
        "can_edit_obras": role in (Roles.ADMIN, Roles.ENGENHEIRO),
        "can_read_financeiro": role in (Roles.ADMIN, Roles.FINANCEIRO),
        # Engenheiro acessa apenas seus próprios pagamentos agendados
        "can_request_pagamentos": role in (Roles.ADMIN, Roles.FINANCEIRO, Roles.ENGENHEIRO),
        "can_manage_own_pagamentos": role == Roles.ENGENHEIRO,
        "can_read_rh_admin": role in (Roles.ADMIN, Roles.FINANCEIRO),
        "can_read_rh_me": role == Roles.FUNCIONARIO,
        "can_prepare_create_obra": role in (Roles.ADMIN, Roles.ENGENHEIRO),
        "can_prepare_update_status": role in (Roles.ADMIN, Roles.ENGENHEIRO, Roles.FINANCEIRO),
        "role": role.value,
    }


def _is_screenshot_blocked(module: str | None, screen_data: dict | None) -> bool:
    if module and module.lower() in _SCREENSHOT_BLOCKED_MODULES:
        return True
    return False


class ArkyContextBuilder:
    def build(
        self,
        user: User,
        screen_data: dict | None,
        selection_data: dict | None,
        ui_state_data: dict | None,
        has_screenshot: bool,
    ) -> SanitizedContext:
        screen = screen_data or {}
        selection = selection_data or {}
        ui_state = ui_state_data or {}

        route = _sanitize_str(screen.get("route", "/"), 200)
        path = _sanitize_str(screen.get("path", "/"), 200)
        title = _sanitize_str(screen.get("title", ""), _MAX_TITLE_LEN)
        module = _sanitize_str(screen.get("module", ""), 50) or None

        entity_type = _sanitize_str(selection.get("entity_type", ""), 50) or None
        entity_id = _sanitize_str(selection.get("entity_id", ""), 36) or None

        filters = _sanitize_filters(ui_state.get("filters"))
        visible_tab = _sanitize_str(ui_state.get("visible_tab", ""), 50) or None

        screenshot_blocked = has_screenshot and _is_screenshot_blocked(module, screen)

        return SanitizedContext(
            route=route,
            path=path,
            title=title,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            filters=filters,
            visible_tab=visible_tab,
            screenshot_included=has_screenshot and not screenshot_blocked,
            screenshot_blocked=screenshot_blocked,
            permission_summary=_build_permission_summary(user),
        )

    def sanitize_message(self, message: str) -> str:
        """Truncate and strip the user message. Content is treated as untrusted."""
        if not isinstance(message, str):
            return ""
        return message[:_MAX_MSG_LEN].strip()
