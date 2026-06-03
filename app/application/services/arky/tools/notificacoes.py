"""Read-only and prepare tools for Notificacoes module."""
from __future__ import annotations

import logging

from app.application.services.arky.tools.context import ArkyToolContext

logger = logging.getLogger(__name__)


async def notificacoes_list(params: dict, ctx: ArkyToolContext) -> dict:
    limit = min(int(params.get("limit", 10)), 20)
    only_unread = bool(params.get("only_unread", False))

    notifs = await ctx.notificacao_service.list_notificacoes(
        user_id=ctx.user.id,
        team_id=ctx.team_id,
        page=1,
        limit=limit,
    )

    items = []
    for n in notifs:
        is_read = getattr(n, "lida", False)
        if only_unread and is_read:
            continue
        items.append({
            "id": str(n.id),
            "mensagem": (getattr(n, "mensagem", "") or "")[:200],
            "lida": is_read,
            "created_at": n.created_at.isoformat() if hasattr(n, "created_at") else None,
        })

    return {
        "total_showing": len(items),
        "only_unread": only_unread,
        "notificacoes": items,
    }


async def notificacoes_prepare_send(params: dict, ctx: ArkyToolContext) -> dict:
    mensagem = (params.get("mensagem") or "").strip()
    obra_id_str = params.get("obra_id")

    if not mensagem:
        return {"error": "mensagem é obrigatória"}
    if len(mensagem) > 1000:
        return {"error": "mensagem muito longa (máx 1000 caracteres)"}

    preview_payload = {
        "mensagem": mensagem,
        "team_id": str(ctx.team_id),
        "user_id": str(ctx.user.id),
    }
    if obra_id_str:
        preview_payload["obra_id"] = obra_id_str

    from app.domain.entities.arky import ArkyActionPreview
    preview = ArkyActionPreview(
        team_id=ctx.team_id,
        user_id=ctx.user.id,
        conversation_id=ctx.team_id,
        action_type="prepare_send_notificacao",
        payload=preview_payload,
        summary=f"Enviar notificação: {mensagem[:80]}{'...' if len(mensagem) > 80 else ''}",
        risk_level="preparacao",
    )

    saved = await ctx.arky_preview_repo.save(preview)
    await ctx.uow.commit()

    return {
        "action_preview_id": str(saved.id),
        "action_type": "prepare_send_notificacao",
        "summary": saved.summary,
        "risk_level": saved.risk_level,
        "requires_confirmation": True,
        "preview": {
            "mensagem": mensagem[:200],
            "obra_id": obra_id_str,
        },
        "expires_in_minutes": 15,
    }
