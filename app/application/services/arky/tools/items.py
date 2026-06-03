"""Read-only and prepare tools for Items module."""
from __future__ import annotations

import logging
from uuid import UUID

from app.application.services.arky.tools.context import ArkyToolContext
from app.domain.errors import DomainError

logger = logging.getLogger(__name__)


async def items_list_by_obra(params: dict, ctx: ArkyToolContext) -> dict:
    obra_id_str = params.get("obra_id", "")
    if not obra_id_str:
        return {"error": "obra_id é obrigatório"}

    try:
        obra_id = UUID(obra_id_str)
    except ValueError:
        return {"error": "obra_id inválido"}

    try:
        # Verify obra belongs to tenant
        obra = await ctx.obra_service.get_obra(obra_id, ctx.team_id)
    except DomainError:
        return {"error": "Obra não encontrada ou sem permissão de acesso"}

    items = await ctx.item_service.list_items(obra_id)

    total = len(items)
    done = sum(1 for i in items if getattr(i, "is_done", False))

    return {
        "obra_id": str(obra_id),
        "obra_title": obra.title,
        "total_items": total,
        "items_concluidos": done,
        "items_pendentes": total - done,
        "items": [
            {
                "id": str(i.id),
                "title": i.title,
                "is_done": getattr(i, "is_done", False),
                "description": (getattr(i, "description", "") or "")[:200],
            }
            for i in items[:30]
        ],
    }


async def items_prepare_create(params: dict, ctx: ArkyToolContext) -> dict:
    obra_id_str = params.get("obra_id", "")
    title = (params.get("title") or "").strip()
    description = (params.get("description") or "").strip()

    if not obra_id_str:
        return {"error": "obra_id é obrigatório"}
    if not title:
        return {"error": "title é obrigatório"}

    try:
        obra_id = UUID(obra_id_str)
    except ValueError:
        return {"error": "obra_id inválido"}

    try:
        obra = await ctx.obra_service.get_obra(obra_id, ctx.team_id)
    except DomainError:
        return {"error": "Obra não encontrada ou sem permissão de acesso"}

    preview_payload = {
        "obra_id": str(obra_id),
        "title": title[:200],
        "description": description[:1000],
        "team_id": str(ctx.team_id),
        "user_id": str(ctx.user.id),
    }

    from app.domain.entities.arky import ArkyActionPreview
    preview = ArkyActionPreview(
        team_id=ctx.team_id,
        user_id=ctx.user.id,
        conversation_id=ctx.team_id,
        action_type="prepare_create_item",
        payload=preview_payload,
        summary=f"Criar item '{title}' na obra '{obra.title}'",
        risk_level="preparacao",
    )

    saved = await ctx.arky_preview_repo.save(preview)
    await ctx.uow.commit()

    return {
        "action_preview_id": str(saved.id),
        "action_type": "prepare_create_item",
        "summary": saved.summary,
        "risk_level": saved.risk_level,
        "requires_confirmation": True,
        "preview": {
            "obra_title": obra.title,
            "item_title": title,
        },
        "expires_in_minutes": 15,
    }
