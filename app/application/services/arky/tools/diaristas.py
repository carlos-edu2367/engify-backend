"""Read-only tools for Diaristas. A chave Pix NUNCA é exposta ao modelo."""
from __future__ import annotations

import logging

from app.application.services.arky.tools.context import ArkyToolContext

logger = logging.getLogger(__name__)

_MAX_LIMIT = 50


async def diaristas_list(params: dict, ctx: ArkyToolContext) -> dict:
    """Lista diaristas do time para ajudar a montar sugestões de pagamento.

    Retorna apenas id, nome e valor da diária — nunca a chave Pix do diarista.
    """
    try:
        limit = min(int(params.get("limit", 30)), _MAX_LIMIT)
    except (TypeError, ValueError):
        limit = 30

    try:
        diaristas = await ctx.diarist_service.list_diarists(
            team_id=ctx.team_id, limit=limit, page=1
        )
    except Exception as e:
        logger.warning("Erro ao listar diaristas: %s", e)
        return {"error": "Não foi possível listar os diaristas"}

    return {
        "total": len(diaristas),
        "diaristas": [
            {
                "id": str(d.id),
                "nome": d.nome,
                "valor_diaria": float(d.valor_diaria),
            }
            for d in diaristas
        ],
    }
