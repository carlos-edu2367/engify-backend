"""
Read-only and prepare tools for the Obras module.
All functions return sanitized dicts safe to send to the model.
team_id always comes from ArkyToolContext (JWT-derived), never from model args.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.application.services.arky.tools.context import ArkyToolContext
from app.domain.entities.obra import Status
from app.domain.errors import DomainError

logger = logging.getLogger(__name__)


def _status_label(status: Status) -> str:
    labels = {
        Status.PLANEJAMENTO: "Planejamento",
        Status.EM_ANDAMENTO: "Em andamento",
        Status.FINANCEIRO: "Financeiro",
        Status.FINALIZADO: "Finalizado",
    }
    return labels.get(status, status.value)


async def obras_get_detail(params: dict, ctx: ArkyToolContext) -> dict:
    obra_id_str = params.get("obra_id", "")
    if not obra_id_str:
        return {"error": "obra_id é obrigatório"}

    try:
        obra_id = UUID(obra_id_str)
    except ValueError:
        return {"error": "obra_id inválido"}

    try:
        obra = await ctx.obra_service.get_obra(obra_id, ctx.team_id)
    except DomainError:
        return {"error": "Obra não encontrada ou sem permissão de acesso"}

    return {
        "id": str(obra.id),
        "title": obra.title,
        "description": obra.description,
        "status": _status_label(obra.status),
        "status_value": obra.status.value,
        "responsavel_id": str(obra.responsavel_id),
        "data_entrega": obra.data_entrega.isoformat() if obra.data_entrega else None,
        "created_date": obra.created_date.isoformat() if obra.created_date else None,
        "has_valor": obra.valor is not None,
    }


async def obras_list(params: dict, ctx: ArkyToolContext) -> dict:
    status_str = params.get("status")
    limit = min(int(params.get("limit", 10)), 20)

    if status_str:
        try:
            status = Status(status_str)
        except ValueError:
            return {"error": f"Status inválido: {status_str}"}
        obras = await ctx.obra_service.list_by_status(ctx.team_id, status, 1, limit)
        total = await ctx.obra_service.count_by_status(ctx.team_id, status)
    else:
        obras = await ctx.obra_service.list_obras(ctx.team_id, 1, limit)
        total = await ctx.obra_service.count_obras(ctx.team_id)

    return {
        "total": total,
        "showing": len(obras),
        "obras": [
            {
                "id": str(o.id),
                "title": o.title,
                "status": _status_label(o.status),
                "status_value": o.status.value,
                "data_entrega": o.data_entrega.isoformat() if o.data_entrega else None,
            }
            for o in obras
        ],
    }


async def obras_prepare_create(params: dict, ctx: ArkyToolContext) -> dict:
    title = (params.get("title") or "").strip()
    description = (params.get("description") or "").strip()
    responsavel_id_str = params.get("responsavel_id", "")

    if not title:
        return {"error": "title é obrigatório"}
    if not description:
        return {"error": "description é obrigatório"}
    if not responsavel_id_str:
        return {"error": "responsavel_id é obrigatório"}

    try:
        UUID(responsavel_id_str)
    except ValueError:
        return {"error": "responsavel_id inválido"}

    preview_payload = {
        "title": title[:200],
        "description": description[:1000],
        "responsavel_id": responsavel_id_str,
        "team_id": str(ctx.team_id),
        "user_id": str(ctx.user.id),
    }

    if params.get("valor") is not None:
        try:
            preview_payload["valor"] = float(params["valor"])
        except (TypeError, ValueError):
            pass

    if params.get("data_entrega"):
        preview_payload["data_entrega"] = str(params["data_entrega"])

    from app.domain.entities.arky import ArkyActionPreview
    preview = ArkyActionPreview(
        team_id=ctx.team_id,
        user_id=ctx.user.id,
        conversation_id=ctx.team_id,  # placeholder; overwritten by orchestrator
        action_type="prepare_create_obra",
        payload=preview_payload,
        summary=f"Criar obra: {title}",
        risk_level="preparacao",
    )

    saved = await ctx.arky_preview_repo.save(preview)
    await ctx.uow.commit()

    return {
        "action_preview_id": str(saved.id),
        "action_type": "prepare_create_obra",
        "summary": saved.summary,
        "risk_level": saved.risk_level,
        "requires_confirmation": True,
        "preview": {
            "title": title,
            "description": description[:200],
            "responsavel_id": responsavel_id_str,
        },
        "expires_in_minutes": 15,
    }


async def obras_prepare_update_status(params: dict, ctx: ArkyToolContext) -> dict:
    obra_id_str = params.get("obra_id", "")
    novo_status_str = params.get("novo_status", "")
    motivo = (params.get("motivo") or "").strip()[:500]

    if not obra_id_str:
        return {"error": "obra_id é obrigatório"}
    if not novo_status_str:
        return {"error": "novo_status é obrigatório"}

    try:
        obra_id = UUID(obra_id_str)
        novo_status = Status(novo_status_str)
    except ValueError as e:
        return {"error": f"Parâmetro inválido: {e}"}

    try:
        obra = await ctx.obra_service.get_obra(obra_id, ctx.team_id)
    except DomainError:
        return {"error": "Obra não encontrada ou sem permissão de acesso"}

    from app.domain.entities.user import Roles
    restricted_transition = (
        obra.status == Status.FINANCEIRO
        and novo_status == Status.FINALIZADO
        and ctx.user.role not in (Roles.ADMIN, Roles.FINANCEIRO)
    )
    if restricted_transition:
        return {
            "error": "Apenas ADMIN ou FINANCEIRO podem finalizar uma obra em status Financeiro"
        }

    if obra.status == novo_status:
        return {"error": f"A obra já está no status '{_status_label(novo_status)}'"}

    preview_payload = {
        "obra_id": str(obra_id),
        "status_atual": obra.status.value,
        "novo_status": novo_status.value,
        "motivo": motivo,
        "team_id": str(ctx.team_id),
        "user_id": str(ctx.user.id),
    }

    from app.domain.entities.arky import ArkyActionPreview
    preview = ArkyActionPreview(
        team_id=ctx.team_id,
        user_id=ctx.user.id,
        conversation_id=ctx.team_id,
        action_type="prepare_update_obra_status",
        payload=preview_payload,
        summary=f"Alterar status de '{obra.title}': {_status_label(obra.status)} → {_status_label(novo_status)}",
        risk_level="escrita_sensivel",
    )

    saved = await ctx.arky_preview_repo.save(preview)
    await ctx.uow.commit()

    return {
        "action_preview_id": str(saved.id),
        "action_type": "prepare_update_obra_status",
        "summary": saved.summary,
        "risk_level": saved.risk_level,
        "requires_confirmation": True,
        "preview": {
            "obra_title": obra.title,
            "status_atual": _status_label(obra.status),
            "novo_status": _status_label(novo_status),
        },
        "expires_in_minutes": 15,
    }
