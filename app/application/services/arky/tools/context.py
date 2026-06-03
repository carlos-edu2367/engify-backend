"""Shared tool execution context."""
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.user import User


@dataclass
class ArkyToolContext:
    user: User
    team_id: UUID
    # Services injected by the orchestrator — may be None if not needed
    obra_service: object | None = None
    item_service: object | None = None
    notificacao_service: object | None = None
    financeiro_fluxo_service: object | None = None
    rh_dashboard_service: object | None = None
    arky_preview_repo: object | None = None
    uow: object | None = None
